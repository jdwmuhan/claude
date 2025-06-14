from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import ContentType, Contents, ContentsAttached
import json
import markdown

def teacher_required(view_func):
    """교사 권한 필요한 뷰 데코레이터"""
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'teacher'):
            messages.error(request, '교사만 접근 가능합니다.')
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@login_required
@teacher_required
def dashboard_view(request):
    """컨텐츠 제작 대시보드"""
    # 컨텐츠 통계
    total_contents = Contents.objects.count()
    recent_contents = Contents.objects.order_by('-created_at')[:5]
    content_types = ContentType.objects.all()
    
    context = {
        'total_contents': total_contents,
        'recent_contents': recent_contents,
        'content_types': content_types,
    }
    
    return render(request, 'cp/dashboard.html', context)

@login_required
@teacher_required
def content_type_list_view(request):
    """컨텐츠 타입 목록"""
    content_types = ContentType.objects.all()
    
    context = {
        'content_types': content_types,
    }
    
    return render(request, 'cp/content_types/list.html', context)

@login_required
@teacher_required
def content_list_view(request):
    """컨텐츠 목록"""
    contents = Contents.objects.all().order_by('-created_at')
    
    # 검색 기능
    search = request.GET.get('search')
    if search:
        contents = contents.filter(title__icontains=search)
    
    # 타입 필터
    content_type_id = request.GET.get('type')
    if content_type_id:
        contents = contents.filter(content_type_id=content_type_id)
    
    # 페이지네이션
    paginator = Paginator(contents, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 컨텐츠 타입 목록 (필터용)
    content_types = ContentType.objects.all()
    
    context = {
        'page_obj': page_obj,
        'contents': page_obj.object_list,
        'content_types': content_types,
        'search': search,
        'selected_type': content_type_id,
    }
    
    return render(request, 'cp/contents/list.html', context)

@login_required
@teacher_required
def content_create_view(request):
    """컨텐츠 생성"""
    if request.method == 'POST':
        try:
            # 마크다운을 HTML로 변환
            markdown_content = request.POST.get('content', '')
            html_content = markdown.markdown(markdown_content, extensions=['extra', 'codehilite'])
            
            content = Contents.objects.create(
                content_type_id=request.POST.get('content_type'),
                title=request.POST.get('title'),
                page=html_content,
                meta_data={
                    'rubric': request.POST.get('rubric', ''),
                    'original_markdown': markdown_content,
                    'choices': request.POST.getlist('choices[]') if request.POST.get('content_type') == '1' else [],
                    'correct_answer': request.POST.get('correct_answer', '')
                }
            )
            
            messages.success(request, f'{content.title} 컨텐츠가 생성되었습니다.')
            return redirect('cp:content_detail', content_id=content.id)
        except Exception as e:
            messages.error(request, f'컨텐츠 생성 중 오류가 발생했습니다: {str(e)}')
    
    content_types = ContentType.objects.all()
    context = {
        'content_types': content_types,
    }
    
    return render(request, 'cp/contents/create.html', context)

@login_required
@teacher_required
def content_edit_view(request, content_id):
    """컨텐츠 편집"""
    content = get_object_or_404(Contents, id=content_id)
    
    if request.method == 'POST':
        try:
            # 마크다운을 HTML로 변환
            markdown_content = request.POST.get('content', '')
            html_content = markdown.markdown(markdown_content, extensions=['extra', 'codehilite'])
            
            content.content_type_id = request.POST.get('content_type')
            content.title = request.POST.get('title')
            content.page = html_content
            content.meta_data = {
                'rubric': request.POST.get('rubric', ''),
                'original_markdown': markdown_content,
                'choices': request.POST.getlist('choices[]') if request.POST.get('content_type') == '1' else [],
                'correct_answer': request.POST.get('correct_answer', '')
            }
            content.save()
            
            messages.success(request, f'{content.title} 컨텐츠가 수정되었습니다.')
            return redirect('cp:content_detail', content_id=content.id)
        except Exception as e:
            messages.error(request, f'컨텐츠 수정 중 오류가 발생했습니다: {str(e)}')
    
    content_types = ContentType.objects.all()
    
    # 기존 마크다운 내용 복원
    original_markdown = content.meta_data.get('original_markdown', '')
    
    context = {
        'content': content,
        'content_types': content_types,
        'original_markdown': original_markdown,
    }
    
    return render(request, 'cp/contents/edit.html', context)

@login_required
@teacher_required
def content_detail_view(request, content_id):
    """컨텐츠 상세"""
    content = get_object_or_404(Contents, id=content_id)
    
    context = {
        'content': content,
    }
    
    return render(request, 'cp/contents/detail.html', context)

@login_required
@teacher_required
def content_preview_view(request, content_id):
    """컨텐츠 미리보기"""
    content = get_object_or_404(Contents, id=content_id)
    
    context = {
        'content': content,
    }
    
    return render(request, 'cp/contents/preview.html', context)

@login_required
@teacher_required
def content_delete_view(request, content_id):
    """컨텐츠 삭제"""
    content = get_object_or_404(Contents, id=content_id)
    
    if request.method == 'POST':
        title = content.title
        content.delete()
        messages.success(request, f'{title} 컨텐츠가 삭제되었습니다.')
        return redirect('cp:content_list')
    
    context = {
        'content': content,
    }
    
    return render(request, 'cp/contents/delete_confirm.html', context)

@login_required
@teacher_required
def editor_view(request):
    """통합 에디터 페이지 (기존 JavaScript 에디터와 호환)"""
    content_types = ContentType.objects.all()
    recent_contents = Contents.objects.order_by('-created_at')[:10]
    
    context = {
        'content_types': content_types,
        'recent_contents': recent_contents,
    }
    
    return render(request, 'cp/editor/index.html', context)

# API Views (기존 JavaScript와 호환성을 위해)
@csrf_exempt
@require_http_methods(["GET"])
def api_content_type_list(request):
    """컨텐츠 타입 목록 API"""
    content_types = ContentType.objects.all()
    return JsonResponse({
        'content_types': [ct.to_dict() for ct in content_types]
    })

@csrf_exempt
@require_http_methods(["POST"])
def api_content_create(request):
    """컨텐츠 생성 API"""
    if not hasattr(request.user, 'teacher'):
        return JsonResponse({'error': '교사만 접근 가능합니다.'}, status=403)
    
    try:
        data = json.loads(request.body)
        
        # 마크다운을 HTML로 변환
        markdown_content = data.get('content', '')
        html_content = markdown.markdown(markdown_content, extensions=['extra', 'codehilite'])
        
        content = Contents.objects.create(
            content_type_id=data.get('content_type'),
            title=data.get('title'),
            page=html_content,
            meta_data={
                'rubric': data.get('rubric', ''),
                'original_markdown': markdown_content,
                'type': data.get('type', ''),
            }
        )
        
        return JsonResponse({
            'success': True,
            'content': content.to_dict()
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["GET"])
def api_content_list(request):
    """컨텐츠 목록 API"""
    contents = Contents.objects.all().order_by('-created_at')[:20]
    return JsonResponse({
        'contents': [content.to_dict() for content in contents]
    })



