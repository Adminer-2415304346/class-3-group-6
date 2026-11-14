"""SZX（第9—10周）：先验证并重新编码图片，再保存；文件路径不采用客户端输入。"""

import io
import logging
import uuid
import warnings

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from djangoblog.maintenance_config import get_maintenance_options

logger = logging.getLogger(__name__)
_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


class ImageUploadRejected(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _validated_image(upload, options):
    limit = options["UPLOAD_MAX_BYTES"]
    if upload.size > limit:
        raise ImageUploadRejected("file_too_large", "图片文件超过大小限制。")
    content = upload.read(limit + 1)
    if len(content) > limit:
        raise ImageUploadRejected("file_too_large", "图片文件超过大小限制。")
    if not content:
        raise ImageUploadRejected("invalid_file", "请选择一张有效图片。")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                image_format = image.format
                if image_format not in options["UPLOAD_ALLOWED_FORMATS"]:
                    raise ImageUploadRejected("invalid_file", "图片格式不在允许列表中。")
                if image.width * image.height > options["UPLOAD_MAX_PIXELS"]:
                    raise ImageUploadRejected("invalid_file", "图片像素超过限制。")
                if getattr(image, "is_animated", False):
                    raise ImageUploadRejected("invalid_file", "请上传静态图片。")
                image.verify()

            # SZX：verify之后重新打开并完整解码，重新编码去除尾随内容与客户端元数据。
            with Image.open(io.BytesIO(content)) as source:
                source.load()
                # SZX：先应用相机方向，再清除元数据，避免竖拍照片旋转错误。
                with ImageOps.exif_transpose(source) as oriented:
                    mode = "RGBA" if (oriented.mode == "RGBA"
                                      or "transparency" in oriented.info) else "RGB"
                    if image_format == "JPEG":
                        mode = "RGB"
                    with oriented.convert(mode) as clean, io.BytesIO() as output:
                        clean.info.clear()
                        clean.save(output, format=image_format)
                        encoded = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ImageUploadRejected("invalid_file", "图片内容无效或已损坏。") from error
    if len(encoded) > limit:
        raise ImageUploadRejected("file_too_large", "处理后的图片超过大小限制。")
    return encoded, image_format


def save_uploaded_image(upload):
    """Return media metadata only after complete validation, re-encoding and storage."""
    encoded, image_format = _validated_image(upload, get_maintenance_options())
    timestamp = timezone.now()
    if timezone.is_aware(timestamp):
        timestamp = timezone.localtime(timestamp)
    day = timestamp.strftime("%Y/%m/%d")
    name = f"images/{day}/{uuid.uuid4().hex}.{_EXTENSIONS[image_format]}"
    with ContentFile(encoded) as content:
        saved_name = default_storage.save(name, content)
    try:
        url = default_storage.url(saved_name)
    except (OSError, NotImplementedError):
        try:
            default_storage.delete(saved_name)
        except OSError as error:
            logger.warning("图片回滚清理失败：%s", type(error).__name__)
        raise
    return {"url": url, "name": saved_name, "size": len(encoded), "format": image_format}
