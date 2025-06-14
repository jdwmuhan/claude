# teacher/views/contents_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
import json

from .models import Contents, ContentType,ChasiSlide
from .forms import ContentsForm

@login_required
def contents_list(request):
    """콘텐츠 목록"""
    # 기본 쿼리셋 - 현재 사용자가 생성한 콘텐츠만
    queryset = Contents.objects.filter(created_by=request.user)
    
    # 콘텐츠 타입 필터
    content_type = request.GET.get('type')
    if content_type:
        queryset = queryset.filter(content_type_id=content_type)
    
    # 검색
    search = request.GET.get('search')
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) | 
            Q(page__icontains=search)
        )
    
    # select_related로 쿼리 최적화
    queryset = queryset.select_related('content_type').order_by('-created_at')
    
    # 페이지네이션
    paginator = Paginator(queryset, 20)  # 페이지당 20개
    page = request.GET.get('page')
    contents = paginator.get_page(page)
    
    context = {
        'contents': contents,
        'content_types': ContentType.objects.filter(is_active=True),
        'selected_type': content_type,
        'search_query': search or '',
        'page_obj': contents,
        'is_paginated': paginator.num_pages > 1,
    }
    
    return render(request, 'teacher/contents/list.html', context)

@login_required
def contents_create(request):
    """콘텐츠 생성"""
    # 차시에서 왔는지 확인
    from_chasi_id = request.GET.get('from_chasi')
    
    if request.method == 'POST':
        form = ContentsForm(request.POST)
        if form.is_valid():
            content = form.save(commit=False)
            content.created_by = request.user
            
            # JSON 필드 처리
            try:
                # meta_data 처리
                meta_data = form.cleaned_data.get('meta_data', '{}')
                if not meta_data or meta_data.strip() == '':
                    content.meta_data = {}
                else:
                    content.meta_data = json.loads(meta_data)
                
                # tags 처리
                tags = form.cleaned_data.get('tags', '{}')
                if not tags or tags.strip() == '':
                    content.tags = {}
                else:
                    content.tags = json.loads(tags)
                    
            except json.JSONDecodeError as e:
                messages.error(request, f'JSON 형식 오류: {str(e)}')
                return render(request, 'teacher/contents/create.html', {
                    'form': form,
                    'from_chasi_id': from_chasi_id
                })
            
            content.save()
            messages.success(request, '콘텐츠가 생성되었습니다.')
            
            # 차시에서 왔으면 다시 차시로
            if from_chasi_id:
                return redirect('teacher:chasi_slide_add', chasi_id=from_chasi_id)
            
            return redirect('teacher:contents_list')
    else:
        form = ContentsForm()
    
    context = {
        'form': form,
        'content_types': ContentType.objects.filter(is_active=True),
        'from_chasi_id': from_chasi_id,
    }
    
    return render(request, 'teacher/contents/create.html', context)

@login_required
def contents_edit(request, content_id):
    """콘텐츠 수정"""
    content = get_object_or_404(Contents, id=content_id, created_by=request.user)
    
    if request.method == 'POST':
        form = ContentsForm(request.POST, instance=content)
        if form.is_valid():
            # JSON 필드 처리
            try:
                meta_data = form.cleaned_data.get('meta_data', '{}')
                if not meta_data or meta_data.strip() == '':
                    content.meta_data = {}
                else:
                    content.meta_data = json.loads(meta_data)
                
                tags = form.cleaned_data.get('tags', '{}')
                if not tags or tags.strip() == '':
                    content.tags = {}
                else:
                    content.tags = json.loads(tags)
                    
            except json.JSONDecodeError as e:
                messages.error(request, f'JSON 형식 오류: {str(e)}')
                return render(request, 'teacher/contents/edit.html', {
                    'form': form,
                    'object': content
                })
            
            form.save()
            messages.success(request, '콘텐츠가 수정되었습니다.')
            return redirect('teacher:contents_list')
    else:
        # 기존 JSON 데이터를 문자열로 변환
        initial_data = {
            'meta_data': json.dumps(content.meta_data, ensure_ascii=False) if content.meta_data else '{}',
            'tags': json.dumps(content.tags, ensure_ascii=False) if content.tags else '{}'
        }
        form = ContentsForm(instance=content, initial=initial_data)
    
    context = {
        'form': form,
        'object': content,
        'content': content,
        'content_types': ContentType.objects.filter(is_active=True),
    }
    
    return render(request, 'teacher/contents/edit.html', context)

@login_required
@require_POST
def contents_delete(request, content_id):
    """콘텐츠 삭제"""
    content = get_object_or_404(Contents, id=content_id, created_by=request.user)
    
    # 이 콘텐츠를 사용하는 슬라이드가 있는지 확인
    slide_count = content.chasislide_set.count()
    if slide_count > 0:
        messages.error(
            request, 
            f'이 콘텐츠는 {slide_count}개의 슬라이드에서 사용 중이므로 삭제할 수 없습니다.'
        )
        return redirect('teacher:contents_list')
    
    content_title = content.title
    content.delete()
    messages.success(request, f'"{content_title}" 콘텐츠가 삭제되었습니다.')
    
    return redirect('teacher:contents_list')

@login_required
def contents_preview(request, content_id):
    """콘텐츠 미리보기 API"""
    content = get_object_or_404(Contents, id=content_id, created_by=request.user)
    
    data = {
        'title': content.title,
        'content_type': content.content_type.type_name,
        'page': content.page,
        'answer': content.answer,
        'tags': content.tags,
        'meta_data': content.meta_data
    }
    
    return JsonResponse(data)


@login_required
def contents_duplicate(request, content_id):
    """콘텐츠 복제"""
    original = get_object_or_404(Contents, id=content_id, created_by=request.user)
    
    # 콘텐츠 복제
    duplicated = Contents.objects.create(
        content_type=original.content_type,
        title=f"{original.title} (복사본)",
        page=original.page,
        answer=original.answer,
        meta_data=original.meta_data,
        tags=original.tags,
        created_by=request.user
    )
    
    messages.success(request, f'"{original.title}" 콘텐츠가 복제되었습니다.')
    
    # return_to 파라미터 확인
    return_to = request.GET.get('return_to')
    slide_id = request.GET.get('slide_id')
    
    if return_to == 'slide_edit' and slide_id:
        # 슬라이드 편집 페이지로 돌아가면서 새 콘텐츠 선택
        slide = get_object_or_404(ChasiSlide, id=slide_id)
        slide.content = duplicated
        slide.save()
        return redirect('teacher:chasi_slide_edit', slide_id=slide_id)
    
    return redirect('teacher:contents_edit', content_id=duplicated.id)