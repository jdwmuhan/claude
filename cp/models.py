from django.db import models
from teacher.models import Course, Chapter,Chasi,Teacher


# class SubChapter(models.Model):
#     """소단원 모델"""
#     subject = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="과목")
#     chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, verbose_name="대단원", related_name="subchapters")
#     sub_chapter_title = models.CharField(max_length=200, verbose_name="소단원명")
#     sub_chapter_order = models.IntegerField(verbose_name="소단원 순서")
#     description = models.TextField(blank=True, verbose_name="소단원 설명")
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         verbose_name = "소단원"
#         verbose_name_plural = "소단원들"
#         unique_together = ['chapter', 'sub_chapter_order']
#         ordering = ['sub_chapter_order']
    
#     def __str__(self):
#         return f"{self.chapter.chapter_title} - {self.sub_chapter_title}"


class ContentType(models.Model):
    """컨텐츠 타입 모델"""
    type_name = models.CharField(max_length=50, unique=True, verbose_name="타입명")
    description = models.TextField(blank=True, verbose_name="설명")
    icon = models.CharField(max_length=50, default="fas fa-file", verbose_name="아이콘 클래스")
    color = models.CharField(max_length=20, default="blue", verbose_name="색상")
    is_active = models.BooleanField(default=True, verbose_name="활성 상태")
    
    class Meta:
        verbose_name = "컨텐츠 타입"
        verbose_name_plural = "컨텐츠 타입들"
        ordering = ['type_name']
    
    def __str__(self):
        return self.type_name
    
    def to_dict(self):
        return {
            'id': self.id,
            'type_name': self.type_name,
            'description': self.description,
            'icon': self.icon,
            'color': self.color
        }

class Contents(models.Model):
    """컨텐츠 모델"""
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="컨텐츠 타입")
    title = models.CharField(max_length=200, verbose_name="제목")
    page = models.TextField(verbose_name="페이지 내용(HTML)")
    meta_data = models.JSONField(default=dict, verbose_name="메타데이터(루브릭)")
    tags = models.CharField(max_length=500, blank=True, verbose_name="태그 (쉼표 구분)")
    difficulty_level = models.IntegerField(default=1, choices=[
        (1, '기초'), (2, '보통'), (3, '심화'), (4, '최고')
    ], verbose_name="난이도")
    estimated_time = models.IntegerField(default=10, verbose_name="예상 소요시간(분)")
    view_count = models.IntegerField(default=0, verbose_name="조회수")
    is_public = models.BooleanField(default=False, verbose_name="공개 여부")
    created_by = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name="작성자")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "컨텐츠"
        verbose_name_plural = "컨텐츠들"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.content_type.type_name} - {self.title}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content_type': self.content_type.type_name,
            'page': self.page,
            'meta_data': self.meta_data,
            'difficulty_level': self.get_difficulty_level_display(),
            'estimated_time': self.estimated_time,
            'tags': self.tags.split(',') if self.tags else [],
            'created_at': self.created_at.isoformat()
        }

class ContentsAttached(models.Model):
    """컨텐츠 첨부파일 모델"""
    contents = models.ForeignKey(Contents, on_delete=models.CASCADE, verbose_name="컨텐츠", related_name="attachments")
    file = models.FileField(upload_to='contents_files/%Y/%m/', verbose_name="파일")
    file_type = models.CharField(max_length=50, verbose_name="파일 타입")
    original_name = models.CharField(max_length=200, verbose_name="원본 파일명")
    file_size = models.IntegerField(verbose_name="파일 크기")
    thumbnail = models.ImageField(upload_to='contents_thumbnails/%Y/%m/', blank=True, null=True, verbose_name="썸네일")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "컨텐츠 첨부파일"
        verbose_name_plural = "컨텐츠 첨부파일들"
        ordering = ['-uploaded_at']

class ChasiSlide(models.Model):
    """차시 슬라이드 모델"""
    chasi = models.ForeignKey(Chasi, on_delete=models.CASCADE, verbose_name="차시", related_name="slides")
    slide_number = models.IntegerField(verbose_name="슬라이드 번호")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="컨텐츠 타입")
    content = models.ForeignKey(Contents, on_delete=models.CASCADE, verbose_name="컨텐츠")
    slide_title = models.CharField(max_length=200, blank=True, verbose_name="슬라이드 제목")
    instructor_notes = models.TextField(blank=True, verbose_name="교사 메모")
    estimated_time = models.IntegerField(default=5, verbose_name="예상 소요시간(분)")
    is_active = models.BooleanField(default=True, verbose_name="활성 상태")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "차시 슬라이드"
        verbose_name_plural = "차시 슬라이드들"
        unique_together = ['chasi', 'slide_number']
        ordering = ['slide_number']
    
    def __str__(self):
        return f"{self.chasi.chasi_title} - 슬라이드 {self.slide_number}"
