from fastapi import APIRouter, Depends, UploadFile

from app.deps import get_verified_user
from app.models import User
from app.uploads import MAX_BYTES, store_image

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", status_code=201)
def upload(file: UploadFile, user: User = Depends(get_verified_user)) -> dict:
    """사진 1장을 올리고 공개 주소를 돌려준다. 글을 쓰는 일의 일부라 이메일 인증을 마친 사용자만 쓴다."""
    # 한도보다 1바이트 더 읽어 초과 여부만 확인한다. 큰 파일 전체를 메모리에 올리지 않는다.
    # shortcut: 파서가 임시 파일로 받은 뒤이므로 아주 큰 본문은 막지 못한다. 프록시의 본문 크기 제한으로 막는다(배포 때).
    data = file.file.read(MAX_BYTES + 1)
    return {"image_url": store_image(data)}
