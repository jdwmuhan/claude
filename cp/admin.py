# cp/admin.py
from django.contrib import admin
from .models import ContentType, Contents, ContentsAttached,  Chasi, ChasiSlide

@admin.register(ContentType)
class ContentTypeAdmin(admin.ModelAdmin):
    list_display = ['type_name', 'description']
    search_fields = ['type_name', 'description']

@admin.register(Contents)
class ContentsAdmin(admin.ModelAdmin):
    list_display = ['title', 'content_type', 'created_at', 'updated_at']
    list_filter = ['content_type', 'created_at', 'updated_at']
    search_fields = ['title', 'page']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('content_type', 'title')
        }),
        ('내용', {
            'fields': ('page',),
            'classes': ('wide',)
        }),
        ('메타데이터', {
            'fields': ('meta_data',),
            'classes': ('collapse', 'wide')
        }),
        ('생성 정보', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ContentsAttached)
class ContentsAttachedAdmin(admin.ModelAdmin):
    list_display = ['contents', 'original_name', 'file_type', 'file_size', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['original_name', 'contents__title']
    readonly_fields = ['uploaded_at']

# @admin.register(SubChapter)
# class SubChapterAdmin(admin.ModelAdmin):
#     list_display = ['sub_chapter_title', 'chapter', 'subject', 'sub_chapter_order']
#     list_filter = ['subject', 'chapter']
#     search_fields = ['sub_chapter_title', 'chapter__chapter_title']
#     ordering = ['subject', 'chapter__chapter_order', 'sub_chapter_order']

# @admin.register(Chasi)
# class ChasiAdmin(admin.ModelAdmin):
#     list_display = ['chasi_title', 'subject', 'chapter', 'sub_chapter', 'chasi_order']
#     list_filter = ['subject', 'chapter', 'sub_chapter']
#     search_fields = ['chasi_title', 'description']
#     ordering = ['subject', 'chapter_order', 'sub_chapter_order', 'chasi_order']

# @admin.register(ChasiSlide)
# class ChasiSlideAdmin(admin.ModelAdmin):
#     list_display = ['chasi', 'slide_number', 'content_type', 'content']
#     list_filter = ['chasi__subject', 'content_type']
#     search_fields = ['chasi__chasi_title', 'content__title']
#     ordering = ['chasi__subject', 'chasi__chasi_order', 'slide_number']
#     raw_id_fields = ['content']