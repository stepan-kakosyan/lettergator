from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views import View
import boto3
from botocore.config import Config
from .models import LetterAttachment
from django.core.exceptions import PermissionDenied


class AttachmentAccessView(View):
    @method_decorator(login_required)
    def get(self, request, attachment_id):
        attachment = get_object_or_404(LetterAttachment, id=attachment_id)
        user = request.user
        # Check if attachment is linked to a PhysicalLetter and user is owner, or user is admin
        owner_id = None
        if hasattr(attachment, 'physical_letter') and attachment.physical_letter:
            owner_id = getattr(attachment.physical_letter, 'user_id', None)
        # Allow if admin or owner
        if not (user.is_staff or user.is_superuser or (owner_id and owner_id == user.id)):
            raise PermissionDenied("You do not have permission to access this file.")

        # Generate a presigned URL for the file with correct signature version
        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', None),
            config=Config(signature_version='s3v4'),
        )
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        key = attachment.file.name
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=300  # 5 minutes
        )
        return JsonResponse({'url': presigned_url})
