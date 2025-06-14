from django.urls import path
from . import views

app_name = 'cp'

urlpatterns = [
    # 대시보드
    path('', views.dashboard_view, name='dashboard'),
    
    # 컨텐츠 타입
    path('content-types/', views.content_type_list_view, name='content_type_list'),
    
    # 컨텐츠 관리
    path('contents/', views.content_list_view, name='content_list'),
    path('contents/create/', views.content_create_view, name='content_create'),
    path('contents/<int:content_id>/', views.content_detail_view, name='content_detail'),
    path('contents/<int:content_id>/edit/', views.content_edit_view, name='content_edit'),
    path('contents/<int:content_id>/preview/', views.content_preview_view, name='content_preview'),
    path('contents/<int:content_id>/delete/', views.content_delete_view, name='content_delete'),
    
    # 에디터
    path('editor/', views.editor_view, name='editor'),
    
    # API
    path('api/content-types/', views.api_content_type_list, name='api_content_type_list'),
    path('api/contents/', views.api_content_list, name='api_content_list'),
    path('api/contents/create/', views.api_content_create, name='api_content_create'),
]