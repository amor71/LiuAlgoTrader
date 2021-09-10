import importlib
import traceback
from abc import ABCMeta, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.tlog import tlog


class Scanner(metaclass=ABCMeta):
    def __init__(
        self,
        name: str,
        data_loader: DataLoader,
        recurrence: Optional[timedelta],
        target_strategy_name: Optional[str],
        data_source: object = None,
    ):
        self.name = name
        self.recurrence = recurrence
        self.target_strategy_name = target_strategy_name
        self.data_loader = data_loader
        self.data_source = data_source

    def __repr__(self):
        return self.name

    @abstractmethod
    async def run(self, back_time: datetime = None) -> List[str]:
        return []

    @classmethod
    def get_supported_scanners(cls):
        return ["momentum"]

    @classmethod
    async def get_scanner(
        cls,
        data_loader: DataLoader,
        scanner_name: str,
        scanner_details: Dict,
    ):
        try:
            spec = importlib.util.spec_from_file_location(  # type: ignore
                "module.name", scanner_details["filename"]
            )
            custom_scanner_module = importlib.util.module_from_spec(spec)  # type: ignore
            spec.loader.exec_module(custom_scanner_module)  # type: ignore
            class_name = scanner_name
            custom_scanner = getattr(custom_scanner_module, class_name)

            if not issubclass(custom_scanner, Scanner):
                tlog(
                    f"custom scanner must inherit from class {Scanner.__name__}"
                )
                exit(0)

            scanner_details.pop("filename")
            if "recurrence" not in scanner_details:
                scanner_object = custom_scanner(
                    data_loader=data_loader,
                    **scanner_details,
                )
            else:
                recurrence = scanner_details.pop("recurrence")
                scanner_object = custom_scanner(
                    data_loader=data_loader,
                    recurrence=timedelta(minutes=recurrence),
                    **scanner_details,
                )
        except FileNotFoundError as e:
            tlog(
                f"[EXCEPTION] {e} : file not found `{scanner_details['filename']}`"
            )
            exit(0)
        except Exception as e:
            tlog(
                f"[Error]exception of type {type(e).__name__} with args {e.args}"
            )
            traceback.print_exc()
            exit(0)

        else:
            return scanner_object
