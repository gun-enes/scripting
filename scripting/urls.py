from django.contrib import admin
from django.urls import path
from . import api


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/document', api.documents),
    path('api/document/<str:doc_id>', api.document_detail),
    path('api/document/<str:doc_id>/path/<path:subpath>', api.document_path),
]
