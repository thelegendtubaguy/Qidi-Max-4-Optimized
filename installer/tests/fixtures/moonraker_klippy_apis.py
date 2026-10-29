# Helper for Moonraker to Klippy API calls.
#
# Copyright (C) 2020 Eric Callahan <arksine.code@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations
import logging
from ..utils import Sentinel
from ..common import WebRequest, APITransport, RequestType

# QIDI modified: Copy file to .cache when print start
import os
import shutil
import json
from .file_manager.file_manager import FileManager

import logging
import zipfile
import traceback
import aiohttp
import time

# Annotation imports
from typing import (
    TYPE_CHECKING,
    Any,
    Union,
    Optional,
    Dict,
    List,
    TypeVar,
    Mapping,
    Callable,
    Coroutine
)
if TYPE_CHECKING:
    from ..confighelper import ConfigHelper
    from ..common import UserInfo
    from .klippy_connection import KlippyConnection as Klippy
    from .file_manager.file_manager import FileManager
    Subscription = Dict[str, Optional[List[Any]]]
    SubCallback = Callable[[Dict[str, Dict[str, Any]], float], Optional[Coroutine]]
    _T = TypeVar("_T")
    from . import database
    MoonrakerDatabase = database.MoonrakerDatabase

INFO_ENDPOINT = "info"
ESTOP_ENDPOINT = "emergency_stop"
LIST_EPS_ENDPOINT = "list_endpoints"
GC_OUTPUT_ENDPOINT = "gcode/subscribe_output"
GCODE_ENDPOINT = "gcode/script"
SUBSCRIPTION_ENDPOINT = "objects/subscribe"
STATUS_ENDPOINT = "objects/query"
OBJ_LIST_ENDPOINT = "objects/list"
REG_METHOD_ENDPOINT = "register_remote_method"

class KlippyAPI(APITransport):
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.klippy: Klippy = self.server.lookup_component("klippy_connection")
        self.fm: FileManager = self.server.lookup_component("file_manager")
        self.eventloop = self.server.get_event_loop()
        app_args = self.server.get_app_args()
        self.version = app_args.get('software_version')
        # Maintain a subscription for all moonraker requests, as
        # we do not want to overwrite them
        self.host_subscription: Subscription = {}
        self.subscription_callbacks: List[SubCallback] = []

        # Register GCode Aliases
        self.server.register_endpoint(
            "/printer/print/pause", RequestType.POST, self._gcode_pause
        )
        self.server.register_endpoint(
            "/printer/print/resume", RequestType.POST, self._gcode_resume
        )
        self.server.register_endpoint(
            "/printer/print/cancel", RequestType.POST, self._gcode_cancel
        )
        self.server.register_endpoint(
            "/printer/print/start", RequestType.POST, self._gcode_start_print
        )
        self.server.register_endpoint(
            "/printer/restart", RequestType.POST, self._gcode_restart
        )
        self.server.register_endpoint(
            "/printer/firmware_restart", RequestType.POST, self._gcode_firmware_restart
        )
        self.server.register_event_handler(
            "server:klippy_disconnect", self._on_klippy_disconnect
        )
        self.server.register_endpoint(
            "/printer/list_endpoints", RequestType.GET, self.list_endpoints
        )
        self.server.register_endpoint(
            "/printer/breakheater", RequestType.POST, self.breakheater
        )
        self.server.register_endpoint(
            "/printer/breakmacro", RequestType.POST, self.breakmacro
        )
        # 断电续打接口
        self.server.register_endpoint(
            "/printer/print/power_off_print", RequestType.POST, self.power_off_print
        )
        self.server.register_endpoint(
            "/printer/multi_color_controller/flow_stop", RequestType.POST, self.multi_color_flow_stop
        )

    def _on_klippy_disconnect(self) -> None:
        self.host_subscription.clear()
        self.subscription_callbacks.clear()

    async def _gcode_pause(self, web_request: WebRequest) -> str:
        return await self.pause_print()

    async def _gcode_resume(self, web_request: WebRequest) -> str:
        return await self.resume_print()

    async def _gcode_cancel(self, web_request: WebRequest) -> str:
        return await self.cancel_print()

    async def _gcode_start_print(self, web_request: WebRequest) -> str:
        filename: str = web_request.get_str('filename')
        user = web_request.get_current_user()
        plateindex: str = web_request.get_str('plateindex', '1')
        uid: str = web_request.get_str('uid', "native")
        need_extract: bool = web_request.get_boolean('need_extract', True)
        # 判断是否是存在fileurl字段，是的话就下载，异步下载+开启打印，直接返回不阻塞，异步下载和开启打印时需要主动推送到mqtt的job主题进度
        file_url: str = web_request.get_str('fileurl', '')
        if file_url:
            # 如果存在 fileurl，开启异步下载+打印任务
            # 发送value参数
            value_ts = web_request.get_json_list('consumable', [])
            logging.info(f"value_ts -> {value_ts}")
            await self.run_gcode(f"SAVE_VARIABLE VARIABLE=enable_box VALUE={int(bool(value_ts))}")
            for index, value_t in enumerate(value_ts, start=0):
                if value_t != -1:
                   await self.run_gcode(f"SAVE_VARIABLE VARIABLE=value_t{index}  VALUE='\"slot{value_t}\"'")
            # await self.run_gcode("G32") # 不在控制调平
            
            self.eventloop.register_callback(
                self._async_download_and_start_print, 
                file_url,            # url
                filename,            # filename
                False,               # wait_klippy_started: 明确传递默认值
                user,                # user: 现在在正确位置
                plateindex,          # plateindex
                uid,                 # uid
                need_extract         # need_extract: 现在在正确位置
            )
            # 直接返回，告诉前端任务已接纳
            return "ok" 
        # 非云切片的任务uid改为native
        return await self.start_print(filename, user=user, plateindex = plateindex, uid = uid, need_extract = need_extract)

    async def _gcode_restart(self, web_request: WebRequest) -> str:
        return await self.do_restart("RESTART")

    async def _gcode_firmware_restart(self, web_request: WebRequest) -> str:
        return await self.do_restart("FIRMWARE_RESTART")

    async def power_off_print(self, web_request: WebRequest) -> Dict[str, Any]:
        database: MoonrakerDatabase = self.server.lookup_component("database")
        script = await database.generate_power_off_print_gcode()
        return await self.run_gcode(script)

    async def multi_color_flow_stop(self, web_request: WebRequest) -> Dict[str, Any]:
        return await self.flow_stop()

    async def _send_klippy_request(
        self,
        method: str,
        params: Dict[str, Any],
        default: Any = Sentinel.MISSING,
        transport: Optional[APITransport] = None
    ) -> Any:
        try:
            req = WebRequest(method, params, transport=transport or self)
            result = await self.klippy.request(req)
        except self.server.error:
            if default is Sentinel.MISSING:
                raise
            result = default
        return result

    async def run_gcode(self,
                        script: str,
                        default: Any = Sentinel.MISSING
                        ) -> str:
        params = {'script': script}
        result = await self._send_klippy_request(
            GCODE_ENDPOINT, params, default)
        return result

    def copy_file_to_cache(self, origin, target):
        stat = os.statvfs("/")
        free_space = stat.f_frsize * stat.f_bfree
        filesize = os.path.getsize(os.path.join(origin))
        if (filesize < free_space):
            shutil.copy(origin, target)
        else:
            msg = "!! Insufficient disk space, unable to read the file."
            self.server.send_event("server:gcode_response", msg)
            raise self.server.error("Insufficient disk space, unable to read the file.", 500)

    async def start_print(
        self,
        filename: str,
        wait_klippy_started: bool = False,
        user: Optional[UserInfo] = None,
        plateindex: str = "1",
        uid: str = "native",
        need_extract: bool = True,
    ) -> str:
        # WARNING: Do not call this method from within the following
        # event handlers when "wait_klippy_started" is set to True:
        # klippy_identified, klippy_started, klippy_ready, klippy_disconnect
        # Doing so will result in "wait_started" blocking for the specifed
        # timeout (default 20s) and returning False.
        # XXX - validate that file is on disk

        # # ------------必要打印前判断---------------
        # timelapse = self.server.lookup_component("timelapse")
        # if timelapse.config['enabled']:
        #     await self.run_gcode("LED_ON")
        # # ------------必要打印前判断---------------

        homedir = os.path.expanduser("~")
        if(need_extract) :
            if os.path.split(filename)[0].split(os.path.sep)[0] != ".cache":
                base_path = os.path.join(homedir, "printer_data")
                gcodes_path = os.path.join(base_path, "gcodes")
                target = os.path.join(".cache", os.path.basename(filename))
                cache_path = os.path.join(base_path, ".cache")
                
                os.makedirs(cache_path, exist_ok=True)
                
                for item in os.listdir(cache_path):
                    item_path = os.path.join(cache_path, item)
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        
                metadata = self.fm.gcode_metadata.metadata.get(filename, None)
                self.copy_file_to_cache(os.path.join(gcodes_path, filename), os.path.join(base_path, target))
                msg = "// metadata=" + json.dumps(metadata)
                self.server.send_event("server:gcode_response", msg)
                    

        script = f'SDCARD_PRINT_FILE FILENAME="{filename}" PLATEINDEX="{plateindex}" UID="{uid}"'
        if wait_klippy_started:
            await self.klippy.wait_started()
        logging.info(f"Requesting Job Start, filename = {filename}")
        ret = await self.run_gcode(script)
        self.server.send_event("klippy_apis:job_start_complete", user)
        return ret


    async def pause_print(
        self, default: Union[Sentinel, _T] = Sentinel.MISSING
    ) -> Union[_T, str]:
        self.server.send_event("klippy_apis:pause_requested")
        logging.info("Requesting job pause...")
        return await self._send_klippy_request(
            "pause_resume/pause", {}, default)

    async def resume_print(
        self, default: Union[Sentinel, _T] = Sentinel.MISSING
    ) -> Union[_T, str]:
        self.server.send_event("klippy_apis:resume_requested")
        logging.info("Requesting job resume...")
        return await self._send_klippy_request(
            "pause_resume/resume", {}, default)

    async def cancel_print(
        self, default: Union[Sentinel, _T] = Sentinel.MISSING
    ) -> Union[_T, str]:
        self.server.send_event("klippy_apis:cancel_requested")
        logging.info("Requesting job cancel...")
        return await self._send_klippy_request(
            "pause_resume/cancel", {}, default)

    async def flow_stop(
        self, default: Union[Sentinel, _T] = Sentinel.MISSING
    ) -> Union[_T, str]:
        logging.info("Cancel multicolor flow queue...")
        return await self._send_klippy_request(
            "multi_color_controller/flow_stop", {}, default)

    async def breakheater(
        self, default: Union[Sentinel, _T] = Sentinel.MISSING
    ) -> Union[_T, str]:
        return await self._send_klippy_request(
            "breakheater", {}, default)

    async def breakmacro(
        self, default: Union[Sentinel, _T] = Sentinel.MISSING
    ) -> Union[_T, str]:
        return await self._send_klippy_request(
            "breakmacro", {}, default)

    async def do_restart(
        self, gc: str, wait_klippy_started: bool = False
    ) -> str:
        # WARNING: Do not call this method from within the following
        # event handlers when "wait_klippy_started" is set to True:
        # klippy_identified, klippy_started, klippy_ready, klippy_disconnect
        # Doing so will result in "wait_started" blocking for the specifed
        # timeout (default 20s) and returning False.
        if wait_klippy_started:
            await self.klippy.wait_started()
        try:
            result = await self.run_gcode(gc)
        except self.server.error as e:
            if str(e) == "Klippy Disconnected":
                result = "ok"
            else:
                raise
        return result
    
    async def _async_download_and_start_print(
        self, 
        url: str, 
        filename: str,
        wait_klippy_started: bool = False,
        user: Optional[UserInfo] = None,
        plateindex: str = "1",
        uid: str = "native",
        need_extract: bool = False,
    ):
        # 1. 尽早初始化可能用到的基础变量，防止后续的作用域异常
        upload_dir = '/home/qidi/printer_data/.cache'
        dest_path = os.path.join(upload_dir, filename) if filename else os.path.join(upload_dir, "unknown.gcode")
        tmp_path = dest_path + ".tmp"
        
        # 基础 payload 初始化
        payload = {
            'jobState': 'downloading',
            'url': url,
            'timestamp': int(time.time()),
            'filename': filename,
            'plateIndex': plateindex,
            'progress': '0',
            'uid': uid
        }

        # 2. 防重入校验：如果正在运行，直接走错误上报并退出
        if getattr(self, '_is_printing_task_running', False):
            logging.warning(f"[CloudPrint] 任务 {uid} 被拒绝：已有任务正在运行")
            payload.update({
                "jobState": "error",
                "failCause": "Another print task is already running",
                "timestamp": int(time.time())
            })
            self.server.send_event("cloud:slice_download_print", payload)
            return

        # 3. 正式加锁
        self._is_printing_task_running = True

        try:
            logging.info(f"[CloudPrint] 收到下载打印请求: filename={filename}, uid={uid}")

            # 4. 清空目录内部（不删除目录本身）
            if os.path.exists(upload_dir):
                for item in os.listdir(upload_dir):
                    item_path = os.path.join(upload_dir, item)
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.unlink(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                    except Exception as clean_err:
                        logging.warning(f"[CloudPrint] 清理缓存项 {item} 失败: {clean_err}")
            else:
                os.makedirs(upload_dir, mode=0o755, exist_ok=True)
            logging.info(f"[CloudPrint] 缓存目录 {upload_dir} 已就绪")

            # 5. 校验文件名和扩展名
            def is_valid_ext(name):
                clean_name = name.split('?')[0]
                ext = os.path.splitext(clean_name)[-1].lower()
                return ext in ['.3mf', '.gcode']

            target_filename = filename
            if not is_valid_ext(target_filename):
                target_filename = url.split("/")[-1].split("?")[0]
            if not is_valid_ext(target_filename):
                raise Exception("filename is not legal")

            # 6. 开始下载流程
            self.server.send_event("cloud:slice_download_print", payload)
            last_reported_progress = -1

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=600)) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP Error: {response.status}")

                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    logging.info(f"[CloudPrint] 开始下载文件, 总大小: {total_size} bytes")

                    def save_chunk(chunk_data):
                        with open(tmp_path, 'ab') as f:
                            f.write(chunk_data)

                    async for chunk in response.content.iter_chunked(64 * 1024):
                        await self.eventloop.run_in_thread(save_chunk, chunk)
                        downloaded_size += len(chunk)
                        
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            if progress % 5 == 0 and progress != last_reported_progress: 
                                payload["progress"] = f'{progress}'
                                payload["timestamp"] = int(time.time())
                                self.server.send_event("cloud:slice_download_print", payload)
                                last_reported_progress = progress

            # 7. 下载校验与更名
            if not os.path.exists(tmp_path):
                raise Exception("临时文件不存在，下载可能未成功")

            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(tmp_path, dest_path)
            
            logging.info(f"[CloudPrint] 下载完成并保存至: {dest_path}")
            
            payload.update({
                "progress": '100',
                "timestamp": int(time.time())
            })
            self.server.send_event("cloud:slice_download_print", payload)

            # 8. 触发打印
            logging.info(f"[CloudPrint] 准备触发打印任务: {filename}")
            await self.start_print(
                filename, 
                wait_klippy_started=wait_klippy_started, 
                user=user, 
                plateindex=plateindex, 
                uid=uid, 
                need_extract=need_extract
            )
            
            payload.update({
                "jobState": "started",
                "timestamp": int(time.time())
            })
            self.server.send_event("cloud:slice_download_print", payload)
            logging.info(f"[CloudPrint] 任务 {uid} 已成功下发给 Klippy")
            
        except Exception as e:
            logging.error(f"[CloudPrint] 任务 {uid} 执行异常: {str(e)}", exc_info=True)
            payload.update({
                "jobState": "error",
                "failCause": str(e),
                "timestamp": int(time.time())
            })
            self.server.send_event("cloud:slice_download_print", payload)
            
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
        finally:
            # 9. 确保无论成功、失败还是重入被拒，最终都能释放锁
            self._is_printing_task_running = False

    async def list_endpoints(self,
                             default: Union[Sentinel, _T] = Sentinel.MISSING
                             ) -> Union[_T, Dict[str, List[str]]]:
        return await self._send_klippy_request(
            LIST_EPS_ENDPOINT, {}, default)

    async def emergency_stop(self) -> str:
        return await self._send_klippy_request(ESTOP_ENDPOINT, {})

    async def get_klippy_info(self,
                              send_id: bool = False,
                              default: Union[Sentinel, _T] = Sentinel.MISSING
                              ) -> Union[_T, Dict[str, Any]]:
        params = {}
        if send_id:
            ver = self.version
            params = {'client_info': {'program': "Moonraker", 'version': ver}}
        return await self._send_klippy_request(INFO_ENDPOINT, params, default)

    async def get_object_list(self,
                              default: Union[Sentinel, _T] = Sentinel.MISSING
                              ) -> Union[_T, List[str]]:
        result = await self._send_klippy_request(
            OBJ_LIST_ENDPOINT, {}, default)
        if isinstance(result, dict) and 'objects' in result:
            return result['objects']
        if default is not Sentinel.MISSING:
            return default
        raise self.server.error("Invalid response received from Klippy", 500)

    async def query_objects(self,
                            objects: Mapping[str, Optional[List[str]]],
                            default: Union[Sentinel, _T] = Sentinel.MISSING
                            ) -> Union[_T, Dict[str, Any]]:
        params = {'objects': objects}
        result = await self._send_klippy_request(
            STATUS_ENDPOINT, params, default)
        if isinstance(result, dict) and "status" in result:
            return result["status"]
        if default is not Sentinel.MISSING:
            return default
        raise self.server.error("Invalid response received from Klippy", 500)

    async def subscribe_objects(
        self,
        objects: Mapping[str, Optional[List[str]]],
        callback: Optional[SubCallback] = None,
        default: Union[Sentinel, _T] = Sentinel.MISSING
    ) -> Union[_T, Dict[str, Any]]:
        # The host transport shares subscriptions amongst all components
        for obj, items in objects.items():
            if obj in self.host_subscription:
                prev = self.host_subscription[obj]
                if items is None or prev is None:
                    self.host_subscription[obj] = None
                else:
                    uitems = list(set(prev) | set(items))
                    self.host_subscription[obj] = uitems
            else:
                self.host_subscription[obj] = items
        params = {"objects": dict(self.host_subscription)}
        result = await self._send_klippy_request(SUBSCRIPTION_ENDPOINT, params, default)
        if isinstance(result, dict) and "status" in result:
            if callback is not None:
                self.subscription_callbacks.append(callback)
            return result["status"]
        if default is not Sentinel.MISSING:
            return default
        raise self.server.error("Invalid response received from Klippy", 500)

    async def subscribe_from_transport(
        self,
        objects: Mapping[str, Optional[List[str]]],
        transport: APITransport,
        default: Union[Sentinel, _T] = Sentinel.MISSING,
    ) -> Union[_T, Dict[str, Any]]:
        params = {"objects": dict(objects)}
        result = await self._send_klippy_request(
            SUBSCRIPTION_ENDPOINT, params, default, transport
        )
        if isinstance(result, dict) and "status" in result:
            return result["status"]
        if default is not Sentinel.MISSING:
            return default
        raise self.server.error("Invalid response received from Klippy", 500)

    async def subscribe_gcode_output(self) -> str:
        template = {'response_template':
                    {'method': "process_gcode_response"}}
        return await self._send_klippy_request(GC_OUTPUT_ENDPOINT, template)

    async def register_method(self, method_name: str) -> str:
        return await self._send_klippy_request(
            REG_METHOD_ENDPOINT,
            {'response_template': {"method": method_name},
             'remote_method': method_name})

    def send_status(
        self, status: Dict[str, Any], eventtime: float
    ) -> None:
        for cb in self.subscription_callbacks:
            self.eventloop.register_callback(cb, status, eventtime)
        self.server.send_event("server:status_update", status)

    def send_moonraker_status(self, status: Dict[str, Any], eventtime: float) -> None:
        # Can't handle status updates.  This should not be called, but
        # we don't want to raise an exception if it is
        pass

def load_component(config: ConfigHelper) -> KlippyAPI:
    return KlippyAPI(config)