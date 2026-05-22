from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .. import storage
from ..models import Attachment, Project


@login_required
@require_http_methods(["POST"])
def attachment_upload(request, pk):
    project = get_object_or_404(Project, pk=pk)
    file = request.FILES.get("file")
    if file is None:
        return HttpResponseBadRequest("No file provided.")
    project_total = Attachment.total_bytes_for_project(project)
    try:
        storage.validate_upload(
            filename=file.name,
            content_type=file.content_type or "",
            size_bytes=file.size,
            project_total=project_total,
        )
    except storage.AttachmentValidationError as e:
        return HttpResponseBadRequest(str(e))
    key = storage.build_object_key(project_id=project.pk, filename=file.name)
    storage.upload_fileobj(file, key, file.content_type or "application/octet-stream")
    Attachment.objects.create(
        project=project,
        file_key=key,
        original_filename=file.name,
        content_type=file.content_type or "",
        size_bytes=file.size,
        uploaded_by=request.user,
    )
    return render(request, "projects/_attachments_list_swap.html", {"project": project})


@login_required
@require_http_methods(["POST"])
def attachment_delete(request, pk):
    a = get_object_or_404(Attachment, pk=pk)
    project = a.project
    storage.delete_object(a.file_key)
    a.delete()
    return render(request, "projects/_attachments_list_swap.html", {"project": project})


@login_required
def attachment_download(request, pk):
    a = get_object_or_404(Attachment, pk=pk)
    url = storage.signed_download_url(a.file_key, filename=a.original_filename)
    return redirect(url)
