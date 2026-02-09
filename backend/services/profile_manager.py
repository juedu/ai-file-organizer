"""분류 프로파일 CRUD 관리 서비스"""

import json
import uuid
import logging
from pathlib import Path
from datetime import datetime

from backend.models import ClassificationProfile, ProfileFolder

logger = logging.getLogger(__name__)

PROFILES_DIR = Path(__file__).parent.parent.parent / "data" / "profiles"

DEFAULT_PROFILES = [
    {
        "name": "기본 파일 정리",
        "description": "파일 종류별 기본 분류",
        "folders": [
            {"name": "사진", "description": "실제 카메라로 촬영한 사진"},
            {"name": "그림", "description": "디지털 아트, 일러스트, 팬아트"},
            {"name": "문서", "description": "PDF, Word, 텍스트 문서"},
            {"name": "스크린샷", "description": "화면 캡처"},
            {"name": "동영상", "description": "비디오 파일"},
            {"name": "음악", "description": "오디오, 음악 파일"},
            {"name": "압축", "description": "압축 파일"},
            {"name": "기타", "description": "위에 해당하지 않는 파일"},
        ],
        "prompt": "이 파일의 종류와 내용을 분석하여 가장 적합한 폴더를 선택하세요.",
        "rename_pattern": "{description}",
        "enable_rename": True,
    },
    {
        "name": "그림 품질 분류",
        "description": "그림의 퀄리티 기준으로 분류",
        "folders": [
            {"name": "명작", "description": "전문가급 퀄리티, 구도와 색감이 뛰어남"},
            {"name": "양호", "description": "평균 이상, 괜찮은 수준"},
            {"name": "보통", "description": "평범한 수준"},
            {"name": "스케치", "description": "러프 스케치, 낙서, 미완성"},
        ],
        "prompt": "이 이미지의 그림 퀄리티를 평가하세요.\n전문가급이면 \"명작\", 괜찮으면 \"양호\", 평범하면 \"보통\", 러프하면 \"스케치\"로 분류하세요.",
        "rename_pattern": "{folder}_{description}",
        "enable_rename": True,
    },
    {
        "name": "이미지 출처 분류",
        "description": "이미지의 출처/용도별 분류",
        "folders": [
            {"name": "직접그린", "description": "본인이 직접 그린 그림, 디지털 아트"},
            {"name": "팬아트", "description": "애니/게임/영화 등의 팬아트"},
            {"name": "짤_밈", "description": "인터넷에서 가져온 재미있는 짤, 밈 이미지"},
            {"name": "스크린샷", "description": "화면 캡처, UI 스크린샷"},
            {"name": "사진", "description": "실제 카메라로 촬영한 사진"},
            {"name": "AI생성", "description": "AI로 생성된 이미지"},
        ],
        "prompt": "이 이미지가 어디서 온 것인지, 어떤 용도인지 판단하세요.",
        "rename_pattern": "{folder}_{description}",
        "enable_rename": True,
    },
    {
        "name": "컨텐츠 수위 분류",
        "description": "이미지의 수위/노출 정도별 분류",
        "folders": [
            {"name": "전체이용가", "description": "누구나 볼 수 있는 안전한 이미지"},
            {"name": "약간노출", "description": "약간의 노출이 있지만 심하지 않음"},
            {"name": "성인", "description": "성인 컨텐츠, 노출이 심함"},
        ],
        "prompt": "이 이미지의 수위/노출 정도를 판단하세요.",
        "rename_pattern": "{description}",
        "enable_rename": False,
    },
    {
        "name": "문서 주제 분류",
        "description": "문서의 주제/용도별 분류",
        "folders": [
            {"name": "업무", "description": "회사 업무 관련 문서, 보고서, 회의록"},
            {"name": "학습", "description": "강의자료, 교재, 학습 노트"},
            {"name": "개인", "description": "개인 메모, 일기, 편지"},
            {"name": "금융", "description": "영수증, 세금, 은행 관련"},
            {"name": "법률계약", "description": "계약서, 법률 문서"},
        ],
        "prompt": "이 문서의 주제와 용도를 분석하세요.",
        "rename_pattern": "{folder}_{description}",
        "enable_rename": True,
    },
    {
        "name": "배경화면 해상도 분류",
        "description": "이미지를 해상도/비율 기준으로 배경화면용 분류",
        "folders": [
            {"name": "4K_와이드", "description": "3840x2160 이상 와이드 스크린 배경화면"},
            {"name": "FHD_와이드", "description": "1920x1080 ~ 3839x2159 와이드 배경화면"},
            {"name": "세로_배경", "description": "세로 비율 이미지 (스마트폰 배경화면 등)"},
            {"name": "정방형", "description": "정사각형 또는 거의 정사각형 비율"},
            {"name": "저해상도", "description": "1280x720 미만의 작은 이미지"},
        ],
        "prompt": "이 이미지의 해상도와 비율을 분석하세요.\n와이드(16:9~21:9)이고 3840 이상이면 4K_와이드,\n와이드이고 1920 이상이면 FHD_와이드,\n세로 비율이면 세로_배경, 정사각형에 가까우면 정방형,\n그 외 작은 이미지는 저해상도로 분류하세요.",
        "rename_pattern": "{description}",
        "enable_rename": True,
    },
    {
        "name": "사진 정리 (촬영 장면별)",
        "description": "실제 사진을 장면/상황별로 분류",
        "folders": [
            {"name": "인물_셀카", "description": "사람 얼굴이 중심인 사진, 셀카, 단체사진"},
            {"name": "풍경_자연", "description": "자연 풍경, 하늘, 바다, 산"},
            {"name": "음식", "description": "음식, 카페, 레스토랑 사진"},
            {"name": "동물", "description": "반려동물, 야생동물 사진"},
            {"name": "일상_기록", "description": "일상 스냅샷, 이벤트, 여행 기록"},
            {"name": "물건_제품", "description": "제품 사진, 물건 촬영, 텍스트 캡처"},
        ],
        "prompt": "이 사진의 주요 피사체와 장면을 분석하여 가장 적합한 분류를 선택하세요.\n사람이 주인공이면 인물_셀카, 자연 경관이면 풍경_자연, 음식이면 음식 등으로 판단하세요.",
        "rename_pattern": "{folder}_{description}",
        "enable_rename": True,
    },
    {
        "name": "다운로드 폴더 정리",
        "description": "다운로드 폴더의 잡다한 파일을 종류별로 정리",
        "folders": [
            {"name": "설치파일", "description": "exe, msi, dmg 등 프로그램 설치 파일"},
            {"name": "문서", "description": "PDF, Word, Excel, PPT 등 문서"},
            {"name": "이미지", "description": "사진, 그림, 아이콘 등 이미지 파일"},
            {"name": "영상_음악", "description": "동영상, 음악, 오디오 파일"},
            {"name": "압축파일", "description": "zip, rar, 7z 등 압축 파일"},
            {"name": "소스코드", "description": "프로그래밍 소스 코드, 스크립트"},
            {"name": "기타", "description": "위 분류에 해당하지 않는 파일"},
        ],
        "prompt": "이 파일의 종류와 용도를 분석하여 가장 적합한 폴더로 분류하세요.\n파일 확장자와 내용을 모두 고려하세요.",
        "rename_pattern": "{description}",
        "enable_rename": True,
    },
    {
        "name": "밈/짤 정리",
        "description": "짤, 밈, 반응 이미지를 감정/용도별 분류",
        "folders": [
            {"name": "웃긴짤", "description": "웃기거나 유머러스한 이미지"},
            {"name": "반응짤", "description": "감정 표현용 리액션 이미지 (놀람, 분노, 슬픔 등)"},
            {"name": "귀여운짤", "description": "귀여운 동물, 캐릭터 이미지"},
            {"name": "정보짤", "description": "정보 전달 목적의 인포그래픽, 캡처"},
            {"name": "기타짤", "description": "기타 분류 어려운 짤"},
        ],
        "prompt": "이 이미지가 어떤 용도의 짤/밈인지 분석하세요.\n웃기면 웃긴짤, 리액션용이면 반응짤, 귀여운 이미지면 귀여운짤, 정보 전달이면 정보짤로 분류하세요.",
        "rename_pattern": "{folder}_{description}",
        "enable_rename": True,
    },
]


class ProfileManager:
    def __init__(self):
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[ClassificationProfile]:
        profiles = []
        for path in sorted(PROFILES_DIR.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profiles.append(ClassificationProfile(**data))
            except Exception as e:
                logger.error("프로파일 로드 실패 %s: %s", path.name, e)
        return profiles

    def get_profile(self, profile_id: str) -> ClassificationProfile | None:
        path = PROFILES_DIR / f"{profile_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ClassificationProfile(**data)
        except Exception as e:
            logger.error("프로파일 로드 실패 %s: %s", profile_id, e)
            return None

    def create_profile(self, data: dict) -> ClassificationProfile:
        now = datetime.now().isoformat()
        profile = ClassificationProfile(
            id=str(uuid.uuid4()),
            name=data["name"],
            description=data.get("description", ""),
            folders=[ProfileFolder(**f) for f in data["folders"]],
            prompt=data["prompt"],
            rename_pattern=data.get("rename_pattern", "{description}"),
            enable_rename=data.get("enable_rename", True),
            is_default=False,
            created_at=now,
            updated_at=now,
        )
        self._save(profile)
        return profile

    def update_profile(self, profile_id: str, data: dict) -> ClassificationProfile | None:
        profile = self.get_profile(profile_id)
        if not profile:
            return None

        if "name" in data:
            profile.name = data["name"]
        if "description" in data:
            profile.description = data["description"]
        if "folders" in data:
            profile.folders = [ProfileFolder(**f) for f in data["folders"]]
        if "prompt" in data:
            profile.prompt = data["prompt"]
        if "rename_pattern" in data:
            profile.rename_pattern = data["rename_pattern"]
        if "enable_rename" in data:
            profile.enable_rename = data["enable_rename"]

        profile.updated_at = datetime.now().isoformat()
        self._save(profile)
        return profile

    def delete_profile(self, profile_id: str) -> bool:
        profile = self.get_profile(profile_id)
        if not profile:
            return False
        if profile.is_default:
            raise ValueError("기본 프로파일은 삭제할 수 없습니다.")
        path = PROFILES_DIR / f"{profile_id}.json"
        path.unlink()
        return True

    def duplicate_profile(self, profile_id: str) -> ClassificationProfile | None:
        original = self.get_profile(profile_id)
        if not original:
            return None

        now = datetime.now().isoformat()
        dup = ClassificationProfile(
            id=str(uuid.uuid4()),
            name=f"{original.name} (사본)",
            description=original.description,
            folders=[f.model_copy() for f in original.folders],
            prompt=original.prompt,
            rename_pattern=original.rename_pattern,
            enable_rename=original.enable_rename,
            is_default=False,
            created_at=now,
            updated_at=now,
        )
        self._save(dup)
        return dup

    def initialize_defaults(self):
        """프로파일이 하나도 없을 때만 기본 5개 생성"""
        if any(PROFILES_DIR.glob("*.json")):
            return

        now = datetime.now().isoformat()
        for d in DEFAULT_PROFILES:
            profile = ClassificationProfile(
                id=str(uuid.uuid4()),
                name=d["name"],
                description=d["description"],
                folders=[ProfileFolder(**f) for f in d["folders"]],
                prompt=d["prompt"],
                rename_pattern=d["rename_pattern"],
                enable_rename=d["enable_rename"],
                is_default=True,
                created_at=now,
                updated_at=now,
            )
            self._save(profile)

        logger.info("기본 프로파일 %d개 생성 완료", len(DEFAULT_PROFILES))

    def _save(self, profile: ClassificationProfile):
        path = PROFILES_DIR / f"{profile.id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile.model_dump(), f, ensure_ascii=False, indent=2)
