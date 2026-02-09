"""설정 관리 모듈 - config.yaml 로드/저장 및 런타임 설정 관리"""

import yaml
from pathlib import Path
from dataclasses import dataclass, field, asdict

CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


@dataclass
class OllamaConfig:
    url: str = "http://127.0.0.1:11434"
    model: str = "huihui_ai/qwen3-vl-abliterated:30b-a3b-instruct"
    timeout: int = 120


@dataclass
class ProcessingConfig:
    operation_mode: str = "copy"
    scan_recursive: bool = False
    skip_hidden: bool = True
    skip_system: bool = True


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 5000


@dataclass
class RemoteConfig:
    """클라이언트 모드: 원격 서버 연결 설정"""
    url: str = ""
    api_key: str = ""


@dataclass
class AppConfig:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    remote: RemoteConfig = field(default_factory=RemoteConfig)
    mode: str = "local"        # local | remote
    api_key: str = ""          # 서버가 클라이언트를 인증할 때 사용하는 키
    language: str = "ko"


_config: AppConfig = AppConfig()


def load_config() -> AppConfig:
    """config.yaml을 읽어 AppConfig 인스턴스로 로드"""
    global _config
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        ollama_data = data.get("ollama", {})
        processing_data = data.get("processing", {})
        server_data = data.get("server", {})
        remote_data = data.get("remote", {})

        _config = AppConfig(
            ollama=OllamaConfig(
                **{k: v for k, v in ollama_data.items()
                   if k in OllamaConfig.__dataclass_fields__}
            ),
            processing=ProcessingConfig(
                **{k: v for k, v in processing_data.items()
                   if k in ProcessingConfig.__dataclass_fields__}
            ),
            server=ServerConfig(
                **{k: v for k, v in server_data.items()
                   if k in ServerConfig.__dataclass_fields__}
            ),
            remote=RemoteConfig(
                **{k: v for k, v in remote_data.items()
                   if k in RemoteConfig.__dataclass_fields__}
            ),
            mode=data.get("mode", "local"),
            api_key=data.get("api_key", ""),
            language=data.get("language", "ko"),
        )
    return _config


def get_config() -> AppConfig:
    """현재 설정 인스턴스 반환"""
    return _config


def save_config(config: AppConfig):
    """설정을 config.yaml에 저장"""
    global _config
    _config = config
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(
            asdict(config), f,
            allow_unicode=True, default_flow_style=False, sort_keys=False
        )
