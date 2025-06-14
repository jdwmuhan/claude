from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg, Prefetch, F
from django.utils import timezone
from django.http import JsonResponse
from functools import wraps
from decimal import Decimal
from django.db import transaction
from django.views.decorators.http import require_POST

from accounts.models import Student
from teacher.models import (
    Course, CourseAssignment, Chapter, SubChapter, 
    Chasi, ChasiSlide, Contents, ContentType
)
from .models import StudentProgress, StudentAnswer, StudentNote,PhysicalResultType,StudentPhysicalResult
from datetime import datetime, timedelta


from .utils import *
from django.db import transaction # 트랜잭션 처리를 위해 추가


def student_required(view_func):
    """학생 권한 필요한 뷰 데코레이터"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, '로그인이 필요합니다.')
            return redirect('accounts:login')
        
        if not hasattr(request.user, 'student'):
            messages.error(request, '학생만 접근 가능합니다.')
            return redirect('accounts:login')
        
        return view_func(request, *args, **kwargs)
    
    return login_required(_wrapped_view)


@login_required
def dashboard_view(request):
    """학생 대시보드 view"""
    student = request.user.student
    
    # 학생에게 할당된 모든 코스를 가져옵니다.
    assigned_courses = CourseAssignment.objects.filter(
        Q(assigned_student=student) | Q(assigned_class=student.school_class)
    ).distinct()
    
    # 할당된 코스 ID 목록을 가져옵니다.
    assigned_course_ids = assigned_courses.values_list('course_id', flat=True)

    # 통계 계산
    completed_slides = StudentProgress.objects.filter(student=student, is_completed=True).count()
    total_slides = ChasiSlide.objects.filter(chasi__sub_chapter__chapter__subject_id__in=assigned_course_ids).count()
    total_records = StudentPhysicalResult.objects.filter(student=student).count()

    stats = {
        'assigned_courses': len(assigned_course_ids),
        'completed_slides': completed_slides,
        'total_slides': total_slides,
        'progress_percent': int((completed_slides / total_slides) * 100) if total_slides > 0 else 0,
        'submitted_answers': StudentAnswer.objects.filter(student=student).count(),
        'total_records': total_records,
    }
    
    # 최근 활동 데이터
    recent_progress = StudentProgress.objects.filter(
        student=student, started_at__isnull=False
    ).select_related('slide__chasi').order_by('-started_at')[:3]

    recent_records = StudentPhysicalResult.objects.filter(
        student=student
    ).select_related('slide__chasi').order_by('-submitted_at')[:3]

    context = {
        'stats': stats,
        'assigned_courses': assigned_courses.select_related('course', 'course__teacher')[:5],
        'recent_progress': recent_progress,
        'recent_records': recent_records,
    }
    
    return render(request, 'student/dashboard.html', context)


@login_required
@student_required
def dashboard_view_0608(request):
    """학생 대시보드"""
    student = request.user.student
    
    # 할당받은 코스들
    assigned_courses = CourseAssignment.objects.filter(
        Q(assigned_student=student) | Q(assigned_class=student.school_class)
    ).select_related('course', 'course__teacher')
    
    # 진행 상황
    my_progress = StudentProgress.objects.filter(student=student)
    
    # 전체 슬라이드 수 계산
    course_ids = assigned_courses.values_list('course_id', flat=True).distinct()
    total_slides = ChasiSlide.objects.filter(
        chasi__sub_chapter__chapter__subject__id__in=course_ids
    ).count()  # .count() 추가!
    
    # 완료한 슬라이드 수
    completed_slides = my_progress.filter(is_completed=True).count()
    
    # 진도율 계산
    if total_slides > 0:
        progress_percent = int((completed_slides / total_slides) * 100)
    else:
        progress_percent = 0
    
    # 통계 데이터
    stats = {
        'assigned_courses': assigned_courses.count(),
        'completed_slides': completed_slides,
        'total_slides': total_slides,
        'progress_percent': progress_percent,
        'submitted_answers': StudentAnswer.objects.filter(student=student).count(),
         # ★★★ 기록된 활동 통계 추가 ★★★
        'total_records': StudentPhysicalResult.objects.filter(student=student).count(),
    }
    
    # 최근 학습한 슬라이드
    recent_progress = StudentProgress.objects.filter(
        student=student, 
        started_at__isnull=False
    ).select_related(
        'slide__chasi__sub_chapter__chapter__subject',
        'slide__content_type'
    ).order_by('-started_at')[:5]

    # 주간 학습 데이터 계산
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())  # 월요일
    
    weekly_data = []
    day_names = ['월', '화', '수', '목', '금', '토', '일']
    
    for i in range(7):
        current_date = start_of_week + timedelta(days=i)
        
        # 해당 날짜에 완료한 슬라이드 수
        completed_count = StudentProgress.objects.filter(
            student=student,
            completed_at__date=current_date,
            is_completed=True
        ).count()
        
        weekly_data.append({
            'day': day_names[i],
            'count': completed_count,
            'percentage': min(completed_count * 5, 100)  # 20개를 100%로 가정
        })

    # ★★★ 최근 신체 기록 요약 추가 ★★★
    recent_records = StudentPhysicalResult.objects.filter(
        student=student
    ).select_related('slide__chasi').order_by('-submitted_at')[:3]
    
    context = {
        'stats': stats,
        'assigned_courses': assigned_courses[:5],
        'recent_progress': recent_progress,
        'weekly_data': weekly_data,
        'recent_records': recent_records, # 컨텍스트에 추가
    }
    
    return render(request, 'student/dashboard.html', context)


# ★★★ '내 기록' 상세 페이지 뷰 추가 ★★★
@login_required
def my_records_view(request):
    """학생의 모든 신체 활동 기록을 보여주는 페이지"""
    student = request.user.student
    records = StudentPhysicalResult.objects.filter(student=student).select_related(
        'slide__chasi__sub_chapter__chapter__subject'
    ).order_by('-submitted_at')

    context = {
        'records': records,
    }
    return render(request, 'student/my_records.html', context)




@login_required
@student_required
def course_list_view(request):
    """내 코스 목록"""
    student = request.user.student
    
    assigned_courses = CourseAssignment.objects.filter(
        Q(assigned_class=student.school_class) | Q(assigned_student=student)
    ).select_related('course', 'course__teacher')
    
    # 각 코스별 진도 계산
    course_data = []
    for assignment in assigned_courses:
        total_slides = ChasiSlide.objects.filter(
            chasi__sub_chapter__chapter__subject=assignment.course,
        ).count()
        
        completed_slides = StudentProgress.objects.filter(
            student=student,
            slide__chasi__sub_chapter__chapter__subject=assignment.course,
            is_completed=True
        ).count()
        
        progress_percent = 0
        if total_slides > 0:
            progress_percent = int((completed_slides / total_slides) * 100)
        
        course_data.append({
            'assignment': assignment,
            'total_slides': total_slides,
            'completed_slides': completed_slides,
            'progress_percent': progress_percent
        })
    
    context = {
        'course_data': course_data,
    }
    
    return render(request, 'student/course_list.html', context)

# ====================================================================
# ★★★ 1. learning_course_view 수정 ★★★
# ====================================================================


@login_required
@student_required
def learning_course_view(request, course_id):
    """코스 학습 페이지 (통계 로직 수정)"""
    student = request.user.student
    course = get_object_or_404(Course, id=course_id)
    
    has_permission = CourseAssignment.objects.filter(
        course=course,
    ).filter(
        Q(assigned_class=student.school_class) | Q(assigned_student=student)
    ).exists()
    
    if not has_permission:
        messages.error(request, '해당 코스에 접근 권한이 없습니다.')
        return redirect('student:course_list')
    
    chapters = course.chapters.all().order_by('chapter_order')
    
    all_slides = ChasiSlide.objects.filter(chasi__sub_chapter__chapter__subject=course, is_active=True)
    total_slides_count = all_slides.count()
    
    completed_slides_count = StudentProgress.objects.filter(
        student=student,
        slide__in=all_slides,
        is_completed=True
    ).count()

    overall_progress = int((completed_slides_count / total_slides_count) * 100) if total_slides_count > 0 else 0

    progress_qs = StudentProgress.objects.filter(student=student, slide__in=all_slides)
    progress_data = {progress.slide_id: progress for progress in progress_qs}
    
    context = {
        'course': course,
        'chapters': chapters,
        'progress_data': progress_data,
        'overall_progress': overall_progress,
        'total_slides': total_slides_count,
        'completed_slides': completed_slides_count,
    }
    
    return render(request, 'student/learning_course.html', context)



@login_required
@student_required
def learning_course_view_0608(request, course_id):
    """코스 학습 페이지 (단순화 버전)"""
    try:
        student = request.user.student
        course = get_object_or_404(Course, id=course_id)
        
        # 권한 확인
        has_permission = CourseAssignment.objects.filter(
            course=course,
        ).filter(
            Q(assigned_class=student.school_class) | Q(assigned_student=student)
        ).exists()
        
        if not has_permission:
            messages.error(request, '해당 코스에 접근 권한이 없습니다.')
            return redirect('student:course_list')
        
        # 간단한 쿼리로 데이터 가져오기
        chapters = course.chapters.all().order_by('chapter_order')
        # ★★★ [수정] 코스 전체의 슬라이드 수와 완료된 슬라이드 수를 효율적인 쿼리로 계산 ★★★
        all_slides = ChasiSlide.objects.filter(chasi__sub_chapter__chapter__subject=course, is_active=True)
        total_slides_count = all_slides.count()
        
        completed_slides_count = StudentProgress.objects.filter(
            student=student,
            slide__in=all_slides,
            is_completed=True
        ).count()

        overall_progress = int((completed_slides_count / total_slides_count) * 100) if total_slides_count > 0 else 0
        
        # 각 대단원의 데이터 확인 (디버깅용)
        for chapter in chapters:
            print(f"Chapter: {chapter.chapter_title}")
            for subchapter in chapter.subchapters.filter(subject=course).order_by('sub_chapter_order'):
                print(f"  SubChapter: {subchapter.sub_chapter_title}")
                for chasi in subchapter.chasis.filter(subject=course, is_published=True).order_by('chasi_order'):
                    print(f"    Chasi: {chasi.chasi_title}")
                    slides = chasi.teacher_slides.filter(is_active=True).order_by('slide_number')
                    print(f"      Slides: {slides.count()}")
                    total_slides += slides.count()
                    
                    # 완료된 슬라이드 계산
                    completed = StudentProgress.objects.filter(
                        student=student,
                        slide__in=slides,
                        is_completed=True
                    ).count()
                    completed_slides += completed
        
        # 진도율 계산
        overall_progress = int((completed_slides / total_slides * 100)) if total_slides > 0 else 0
        
        # 진도 데이터
        progress_qs = StudentProgress.objects.filter(
            student=student,
            slide__chasi__sub_chapter__chapter__subject=course
        ).select_related('slide')
        
        progress_data = {}
        for progress in progress_qs:
            progress_data[progress.slide.id] = progress
        
        context = {
            'course': course,
            'chapters': chapters,
            'progress_data': progress_data,
            'overall_progress': overall_progress,
            'total_slides': total_slides,
            'completed_slides': completed_slides,
            'debug': True,  # 디버깅 모드
        }
        
        return render(request, 'student/learning_course.html', context)
        
    except Exception as e:
        import traceback
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        messages.error(request, f'오류가 발생했습니다: {str(e)}')
        return redirect('student:course_list')





@login_required
@student_required
def slide_view(request, slide_id):
    """슬라이드 학습 페이지"""
    try:
        student = request.user.student
        
        # 슬라이드 조회
        slide = get_object_or_404(
            ChasiSlide.objects.select_related(
                'chasi__sub_chapter__chapter__subject',
                'content',
                'content_type'
            ),
            id=slide_id
        )
        
        # 코스 가져오기
        course = slide.chasi.sub_chapter.chapter.subject
        
        # 권한 확인
        has_access = CourseAssignment.objects.filter(
            course=course
        ).filter(
            Q(assigned_class=student.school_class) | Q(assigned_student=student)
        ).exists()
        
        if not has_access:
            messages.error(request, '해당 슬라이드에 접근 권한이 없습니다.')
            return redirect('student:course_list')
        
        # 진도 체크 및 생성
        progress, created = StudentProgress.objects.get_or_create(
            student=student,
            slide=slide,
            defaults={'view_count': 0}
        )
        
        # 처음 시작하는 경우
        if not progress.started_at:
            progress.started_at = timezone.now()
        
        # 조회수 증가
        progress.view_count = getattr(progress, 'view_count', 0) + 1
        progress.save()
        
        # 기존 답안 확인 - 가장 최근 답안
        existing_answer = StudentAnswer.objects.filter(
            student=student,
            slide=slide
        ).order_by('-submitted_at').first()

         # ★★★ 추가된 로직 ★★★
        # 이미 정답을 맞혔는지 여부를 확인
        is_already_correct = False
        if existing_answer and existing_answer.is_correct:
            is_already_correct = True
        
        # 노트 가져오기
        note = StudentNote.objects.filter(
            student=student,
            slide=slide
        ).first()

        # ★★★ POST 요청 처리 - 문제가 없는 콘텐츠의 '완료' 버튼 처리 ★★★
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'complete':
                # 문제가 없는 슬라이드의 진도 완료 처리
                if not progress.is_completed:
                    progress.is_completed = True
                    progress.completed_at = timezone.now()
                    progress.save()
                    messages.success(request, '학습을 완료했습니다.')
                    
                # 다음 슬라이드로 이동
                next_slide = ChasiSlide.objects.filter(
                    chasi=slide.chasi,
                    slide_number__gt=slide.slide_number
                ).order_by('slide_number').first()
                
                if next_slide:
                    return redirect('student:slide_view', slide_id=next_slide.id)
                else:
                    return redirect('student:learning_course', course_id=course.id)
        
        
        # # 답안 제출 처리
        # if request.method == 'POST':
        #     action = request.POST.get('action')
            
        #     if action == 'submit_answer' and slide.content.answer:
        #         answer = request.POST.get('answer', '').strip()
                
        #         if answer:
        #             # 새로운 답안 생성 (여러 번 제출 가능)
        #             student_answer = StudentAnswer.objects.create(
        #                 student=student,
        #                 slide=slide,
        #                 answer=answer
        #             )
                    
        #             # 자동 채점 (단답형/객관식)
        #             correct_answer = slide.content.answer.strip()
                    
        #             if slide.content_type.type_name in ['단답형', '객관식']:
        #                 is_correct = answer == correct_answer
        #                 student_answer.is_correct = is_correct
        #                 student_answer.score = 100.0 if is_correct else 0.0
        #                 student_answer.save()
                        
        #                 if is_correct:
        #                     messages.success(request, '정답입니다! 잘했어요!')
        #                 else:
        #                     messages.error(request, f'오답입니다. 정답은 "{correct_answer}"입니다.')
        #             else:
        #                 # 서술형은 수동 채점 필요
        #                 messages.success(request, '답안이 제출되었습니다. 선생님이 확인 후 점수를 매길 예정입니다.')
                    
        #             # 문제가 있는 슬라이드를 완료 처리
        #             if not progress.is_completed:
        #                 progress.is_completed = True
        #                 progress.completed_at = timezone.now()
        #                 progress.save()
                    
        #             # 답안 제출 후 existing_answer 업데이트
        #             existing_answer = student_answer
        #         else:
        #             messages.error(request, '답안을 입력해주세요.')
            
        #     elif action == 'complete':
        #         # 진도 완료 처리 (문제가 없는 슬라이드)
        #         if not progress.is_completed:
        #             progress.is_completed = True
        #             progress.completed_at = timezone.now()
        #             progress.save()
        #             messages.success(request, '학습을 완료했습니다.')
        
        # 이전/다음 슬라이드
        prev_slide = ChasiSlide.objects.filter(
            chasi=slide.chasi,
            slide_number__lt=slide.slide_number
        ).order_by('-slide_number').first()
        
        next_slide = ChasiSlide.objects.filter(
            chasi=slide.chasi,
            slide_number__gt=slide.slide_number
        ).order_by('slide_number').first()
        
        # 현재 슬라이드 위치
        total_slides_in_chasi = slide.chasi.teacher_slides.count()
        
        # 객관식 옵션 처리 - content의 meta_data 필드 확인
        options = []
        if slide.content_type.type_name == 'multiple-choice':
            # content.meta_data가 딕셔너리인지 확인
            if hasattr(slide.content, 'meta_data') and isinstance(slide.content.meta_data, dict):
                options = slide.content.meta_data.get('options', [])
        
        context = {
            'slide': slide,
            'progress': progress,
            'existing_answer': existing_answer,
            'note': note,
            'prev_slide': prev_slide,
            'next_slide': next_slide,
            'total_slides_in_chasi': total_slides_in_chasi,
            'options': options,
            'course': course,
            'is_already_correct': is_already_correct, # ★★★ 컨텍스트에 추가 ★★★
        }
        
        return render(request, 'student/slide_view.html', context)
        
    except Exception as e:
        import traceback
        print(f"Error in slide_view: {str(e)}")
        print(traceback.format_exc())
        messages.error(request, f'오류가 발생했습니다: {str(e)}')
        return redirect('student:course_list')


@login_required
@student_required
def progress_view(request):
    """학습 진도 현황"""
    student = request.user.student
    
    # 코스별 진도
    assigned_courses = CourseAssignment.objects.filter(
        Q(assigned_class=student.school_class) | Q(assigned_student=student)
    ).select_related('course')
    
    course_progress = []
    total_all_slides = 0
    total_all_completed = 0
    
    for assignment in assigned_courses:
        course = assignment.course
        
        # 전체 슬라이드 수
        total_slides = ChasiSlide.objects.filter(
            chasi__sub_chapter__chapter__subject=course
        ).count()
        
        # 완료한 슬라이드 수
        completed_slides = StudentProgress.objects.filter(
            student=student,
            slide__chasi__sub_chapter__chapter__subject=course,
            is_completed=True
        ).count()
        
        # 평균 점수
        avg_score_result = StudentAnswer.objects.filter(
            student=student,
            slide__chasi__sub_chapter__chapter__subject=course,
            score__isnull=False
        ).aggregate(avg=Avg('score'))
        
        avg_score = avg_score_result['avg'] if avg_score_result['avg'] else 0
        
        # 진도율 계산
        progress_percent = 0
        if total_slides > 0:
            progress_percent = int((completed_slides / total_slides) * 100)
        
        # 진행 중인 슬라이드 수
        in_progress = StudentProgress.objects.filter(
            student=student,
            slide__chasi__sub_chapter__chapter__subject=course,
            is_completed=False,
            started_at__isnull=False
        ).count()
        
        # 미시작 슬라이드 수
        not_started = total_slides - completed_slides - in_progress
        
        # 전체 통계를 위한 누적
        total_all_slides += total_slides
        total_all_completed += completed_slides
        
        course_progress.append({
            'course': course,
            'total_slides': total_slides,
            'completed_slides': completed_slides,
            'in_progress': in_progress,
            'not_started': not_started,
            'progress_percent': progress_percent,
            'avg_score': round(float(avg_score), 1) if avg_score else 0,
            # 진도에 따른 색상 클래스 추가
            'progress_color': 'green' if progress_percent >= 80 else 'blue' if progress_percent >= 50 else 'yellow' if progress_percent > 0 else 'gray'
        })
    
    # 전체 진도율 계산
    overall_progress_percent = 0
    if total_all_slides > 0:
        overall_progress_percent = int((total_all_completed / total_all_slides) * 100)
    
    # 최근 학습 기록
    recent_activities = StudentProgress.objects.filter(
        student=student
    ).select_related(
        'slide__chasi__sub_chapter__chapter__subject',
        'slide__content_type'
    ).order_by('-started_at')[:20]
    
    # 학습 시간 계산 (실제로는 더 정교한 로직 필요)
    total_study_sessions = StudentProgress.objects.filter(
        student=student,
        completed_at__isnull=False
    ).count()
    
    # 평균 학습 시간 (분 단위로 가정)
    avg_session_time = 15  # 슬라이드당 평균 15분 가정
    total_study_hours = int((total_study_sessions * avg_session_time) / 60)
    
    # 완료한 코스 수
    completed_courses = 0
    for progress in course_progress:
        if progress['progress_percent'] == 100:
            completed_courses += 1
    
    # 평균 점수 계산
    all_scores = StudentAnswer.objects.filter(
        student=student,
        score__isnull=False
    ).aggregate(avg=Avg('score'))
    overall_avg_score = round(float(all_scores['avg']), 1) if all_scores['avg'] else 0
    
    context = {
        'course_progress': course_progress,
        'recent_activities': recent_activities,
        'total_study_time': total_study_hours,
        'overall_progress_percent': overall_progress_percent,
        'total_all_slides': total_all_slides,
        'total_all_completed': total_all_completed,
        'completed_courses': completed_courses,
        'total_courses': len(course_progress),
        'overall_avg_score': overall_avg_score,
    }
    
    return render(request, 'student/progress.html', context)

@login_required
@student_required
def progress_view_0608(request):
    """학습 진도 현황"""
    student = request.user.student
    
    # 코스별 진도
    assigned_courses = CourseAssignment.objects.filter(
        Q(assigned_class=student.school_class) | Q(assigned_student=student)
    ).select_related('course')
    
    course_progress = []
    for assignment in assigned_courses:
        course = assignment.course
        
        # 전체 슬라이드 수
        total_slides = ChasiSlide.objects.filter(
            chasi__sub_chapter__chapter__subject=course
        ).count()
        
        # 완료한 슬라이드 수
        completed_slides = StudentProgress.objects.filter(
            student=student,
            slide__chasi__sub_chapter__chapter__subject=course,
            is_completed=True
        ).count()
        
        # 평균 점수
        avg_score_result = StudentAnswer.objects.filter(
            student=student,
            slide__chasi__sub_chapter__chapter__subject=course,
            score__isnull=False
        ).aggregate(avg=Avg('score'))
        
        avg_score = avg_score_result['avg'] if avg_score_result['avg'] else 0
        
        # 진도율 계산
        progress_percent = 0
        if total_slides > 0:
            progress_percent = int((completed_slides / total_slides) * 100)
        
        # 진행 중인 슬라이드 수
        in_progress = StudentProgress.objects.filter(
            student=student,
            slide__chasi__sub_chapter__chapter__subject=course,
            is_completed=False,
            started_at__isnull=False
        ).count()
        
        # 미시작 슬라이드 수
        not_started = total_slides - completed_slides - in_progress
        
        course_progress.append({
            'course': course,
            'total_slides': total_slides,
            'completed_slides': completed_slides,
            'in_progress': in_progress,
            'not_started': not_started,
            'progress_percent': progress_percent,
            'avg_score': round(float(avg_score), 1) if avg_score else 0,
        })
    
    # 최근 학습 기록
    recent_activities = StudentProgress.objects.filter(
        student=student
    ).select_related(
        'slide__chasi__sub_chapter__chapter__subject',
        'slide__content_type'
    ).order_by('-started_at')[:20]
    
    # 학습 통계
    total_study_time = StudentProgress.objects.filter(
        student=student,
        completed_at__isnull=False
    ).count()  # 실제로는 시간 계산 로직 필요
    
    context = {
        'course_progress': course_progress,
        'recent_activities': recent_activities,
        'total_study_time': total_study_time,
    }
    
    return render(request, 'student/progress.html', context)




####################### 과거 0608==========================
@login_required
@student_required
@require_POST
def check_answer(request):
    """
    학생 답안을 채점하고 저장하는 AJAX 뷰.
    'multiple-choice', 'multi-choice', 'short-answer', 'multi-input' 유형을 모두 처리합니다.
    """
    try:
        # 1. 공통 데이터 가져오기 및 객체 조회
        content_id = request.POST.get('content_id')
        slide_id = request.POST.get('slide_id')

        if not all([content_id, slide_id]):
            return JsonResponse({
                'status': 'error',
                'message': '필수 데이터(content_id, slide_id)가 누락되었습니다.',
            }, status=400)

        student = request.user.student
        slide = get_object_or_404(
            ChasiSlide.objects.select_related('content', 'content_type'),
            id=slide_id
        )
        content = slide.content
        content_type = slide.content_type.type_name

        # 슬라이드와 콘텐츠 ID 일치 여부 확인
        if str(content.id) != content_id:
            return JsonResponse({
                'status': 'error',
                'message': '슬라이드와 콘텐츠 정보가 일치하지 않습니다.',
            }, status=400)
        
        # StudentProgress 가져오기 또는 생성
        progress, created = StudentProgress.objects.get_or_create(
            student=student,
            slide=slide,
            defaults={'started_at': timezone.now()}
        )

        # 2. 콘텐츠 유형에 따른 분기 처리
        
        # ----------------------------------------------------------------------
        #  ★★★★★  새로운 'multi-choice' 유형 처리 (다중 선택)  ★★★★★
        # ----------------------------------------------------------------------
        if content_type == 'multi-choice':
            student_answer_json = request.POST.get('student_answer')
            if not student_answer_json:
                return JsonResponse({'status': 'error', 'message': '답안이 선택되지 않았습니다.'}, status=400)

            try:
                # 학생 답안 파싱 (JSON 문자열 -> 리스트)
                student_answers = json.loads(student_answer_json)
                if not isinstance(student_answers, list):
                    return JsonResponse({'status': 'error', 'message': '잘못된 답안 형식입니다.'}, status=400)
                
                # 정답 파싱 (정답도 콤마로 구분된 문자열 형태일 수 있음)
                correct_answer_str = parse_correct_answer(content.answer)
                # "1,2,3" 형태의 문자열을 리스트로 변환
                correct_answers = [ans.strip() for ans in correct_answer_str.split(',')]
                correct_answers.sort()  # 정렬하여 순서 무관하게 비교
                
                # 학생 답안도 문자열로 변환하고 정렬
                student_answers_str = [str(ans) for ans in student_answers]
                student_answers_str.sort()
                
                # 정답 여부 판단
                is_correct = (student_answers_str == correct_answers)
                score = 100.0 if is_correct else 0.0
                
                # DB에 저장할 데이터 구조
                answer_data = {
                    'selected_answers': student_answers_str,
                    'correct_answers': correct_answers,
                    'is_multiple': True
                }

                # DB에 저장
                student_answer_obj, created = StudentAnswer.objects.update_or_create(
                    student=student,
                    slide=slide,
                    defaults={
                        'answer': answer_data,
                        'is_correct': is_correct,
                        'score': score,
                        'feedback': '다중 선택 문제 자동 채점 완료',
                    }
                )

                # 정답인 경우 StudentProgress 완료 처리
                if is_correct and not progress.is_completed:
                    progress.is_completed = True
                    progress.completed_at = timezone.now()
                    progress.save()

                response_data = {
                    'status': 'success',
                    'is_correct': is_correct,
                    'correct_answers': correct_answers,
                    'student_answers': student_answers_str,
                    'score': score,
                    'submitted_at': student_answer_obj.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'feedback': student_answer_obj.feedback,
                }
                return JsonResponse(response_data)

            except (json.JSONDecodeError, ValueError) as e:
                return JsonResponse({'status': 'error', 'message': f'답안 처리 중 오류 발생: {e}'}, status=400)

        # ----------------------------------------------------------------------
        #  ★★★★★  'multi-input' 유형 처리  ★★★★★
        # ----------------------------------------------------------------------
        elif content_type == 'multi-input':
            student_answer_json = request.POST.get('student_answer')
            if not student_answer_json:
                return JsonResponse({'status': 'error', 'message': '답안 데이터가 없습니다.'}, status=400)

            try:
                # 학생 답안과 정답 데이터 파싱
                student_answers = json.loads(student_answer_json)
                correct_answers_data = json.loads(content.answer)
                correct_answers = correct_answers_data.get('answer', {})

                results = {}
                correct_count = 0
                total_count = len(correct_answers)

                # 개별 문항 채점
                for key, correct_val in correct_answers.items():
                    user_val = student_answers.get(key, "").strip()
                    is_item_correct = (user_val == correct_val)
                    if is_item_correct:
                        correct_count += 1
                    results[key] = {'is_correct': is_item_correct, 'user_answer': user_val}

                # 최종 점수 및 상태 계산
                score = round((correct_count / total_count) * 100) if total_count > 0 else 0
                is_overall_correct = (score == 100)

                # DB에 저장할 데이터 구조 생성
                answer_data_to_save = {
                    'submitted_answers': student_answers,
                    'results': results,
                }

                # DB에 저장 (update_or_create)
                student_answer_obj, created = StudentAnswer.objects.update_or_create(
                    student=student,
                    slide=slide,
                    defaults={
                        'answer': answer_data_to_save,
                        'is_correct': is_overall_correct,
                        'score': score,
                        'feedback': 'multi-input 자동 채점 완료',
                    }
                )

                # 정답인 경우 StudentProgress 완료 처리
                if is_overall_correct and not progress.is_completed:
                    progress.is_completed = True
                    progress.completed_at = timezone.now()
                    progress.save()

                # 클라이언트에 보낼 응답 데이터 구성
                response_data = {
                    'status': 'success',
                    'is_correct': is_overall_correct,
                    'score': score,
                    'results': results,
                    'submitted_at': student_answer_obj.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                }
                return JsonResponse(response_data)

            except (json.JSONDecodeError, KeyError) as e:
                return JsonResponse({'status': 'error', 'message': f'데이터 처리 중 오류 발생: {e}'}, status=400)

        # --------------------------------------------------------------------------
        #  ★★★★★  기존 'multiple-choice', 'short-answer' 유형 처리  ★★★★★
        # --------------------------------------------------------------------------
        elif content_type in ['multiple-choice', 'short-answer']:
            student_answer_str = request.POST.get('student_answer', '').strip()
            if not student_answer_str:
                return JsonResponse({'status': 'error', 'message': '답안이 입력되지 않았습니다.'}, status=400)

            correct_answer = parse_correct_answer(content.answer)
            is_correct = (student_answer_str == correct_answer)
            score = 100.0 if is_correct else 0.0
            
            answer_data = {
                'selected_answer': student_answer_str,
                'correct_answer': correct_answer,
            }

            student_answer_obj, created = StudentAnswer.objects.update_or_create(
                student=student,
                slide=slide,
                defaults={
                    'answer': answer_data,
                    'is_correct': is_correct,
                    'score': score,
                    'feedback': '자동 채점 완료',
                }
            )

            # 정답인 경우 StudentProgress 완료 처리
            if is_correct and not progress.is_completed:
                progress.is_completed = True
                progress.completed_at = timezone.now()
                progress.save()

            response_data = {
                'status': 'success',
                'is_correct': is_correct,
                'correct_answer': correct_answer,
                'student_answer': student_answer_str,
                'score': student_answer_obj.score,
                'submitted_at': student_answer_obj.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                'feedback': student_answer_obj.feedback,
            }
            return JsonResponse(response_data)
            
        else:
            # 지원하지 않는 문제 유형 처리
            return JsonResponse({'status': 'error', 'message': f"지원하지 않는 문제 유형입니다: {content_type}"}, status=400)

    # 3. 모든 예외에 대한 공통 처리
    except ChasiSlide.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '요청한 슬라이드를 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        import traceback
        print(f"ERROR: check_answer 뷰에서 예외 발생: {str(e)}")
        print(f"트레이스백: {traceback.format_exc()}")
        return JsonResponse({
            'status': 'error',
            'message': f'서버 오류가 발생했습니다: {str(e)}',
        }, status=500)





@login_required
@student_required
@require_POST
def check_answer_0612(request):
    """
    학생 답안을 채점하고 저장하는 AJAX 뷰.
    'multiple-choice', 'short-answer', 'multi-input' 유형을 모두 처리합니다.
    """
    try:
        # 1. 공통 데이터 가져오기 및 객체 조회
        content_id = request.POST.get('content_id')
        slide_id = request.POST.get('slide_id')

        # student_answer는 유형에 따라 다르게 처리되므로 여기서는 검증하지 않음
        if not all([content_id, slide_id]):
            return JsonResponse({
                'status': 'error',
                'message': '필수 데이터(content_id, slide_id)가 누락되었습니다.',
            }, status=400)

        student = request.user.student
        slide = get_object_or_404(
            ChasiSlide.objects.select_related('content', 'content_type'),
            id=slide_id
        )
        content = slide.content
        content_type = slide.content_type.type_name

        # 슬라이드와 콘텐츠 ID 일치 여부 확인
        if str(content.id) != content_id:
            return JsonResponse({
                'status': 'error',
                'message': '슬라이드와 콘텐츠 정보가 일치하지 않습니다.',
            }, status=400)
        
        # ★★★ StudentProgress 가져오기 또는 생성 ★★★
        progress, created = StudentProgress.objects.get_or_create(
            student=student,
            slide=slide,
            defaults={'started_at': timezone.now()}
        )

        # 2. 콘텐츠 유형에 따른 분기 처리
        
        # ----------------------------------------------------------------------
        #  ★★★★★  새로운 'multi-input' 유형 처리  ★★★★★
        # ----------------------------------------------------------------------
        if content_type == 'multi-input':
            student_answer_json = request.POST.get('student_answer')
            if not student_answer_json:
                return JsonResponse({'status': 'error', 'message': '답안 데이터가 없습니다.'}, status=400)

            try:
                # 학생 답안과 정답 데이터 파싱
                student_answers = json.loads(student_answer_json)
                correct_answers_data = json.loads(content.answer)
                correct_answers = correct_answers_data.get('answer', {})

                results = {}
                correct_count = 0
                total_count = len(correct_answers)

                # 개별 문항 채점
                for key, correct_val in correct_answers.items():
                    user_val = student_answers.get(key, "").strip()
                    is_item_correct = (user_val == correct_val)
                    if is_item_correct:
                        correct_count += 1
                    results[key] = {'is_correct': is_item_correct, 'user_answer': user_val}

                # 최종 점수 및 상태 계산
                score = round((correct_count / total_count) * 100) if total_count > 0 else 0
                is_overall_correct = (score == 100)

                # DB에 저장할 데이터 구조 생성
                answer_data_to_save = {
                    'submitted_answers': student_answers,
                    'results': results,
                }

                # DB에 저장 (update_or_create)
                student_answer_obj, created = StudentAnswer.objects.update_or_create(
                    student=student,
                    slide=slide,
                    defaults={
                        'answer': answer_data_to_save,
                        'is_correct': is_overall_correct,
                        'score': score,
                        'feedback': 'multi-input 자동 채점 완료',
                    }
                )

                
                # ★★★ 정답인 경우 StudentProgress 완료 처리 ★★★
                if is_overall_correct and not progress.is_completed:
                    progress.is_completed = True
                    progress.completed_at = timezone.now()
                    progress.save()

                # 클라이언트에 보낼 응답 데이터 구성
                response_data = {
                    'status': 'success',
                    'is_correct': is_overall_correct,
                    'score': score,
                    'results': results,
                    'submitted_at': student_answer_obj.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                }
                return JsonResponse(response_data)

            except (json.JSONDecodeError, KeyError) as e:
                return JsonResponse({'status': 'error', 'message': f'데이터 처리 중 오류 발생: {e}'}, status=400)

        # --------------------------------------------------------------------------
        #  ★★★★★  기존 'multiple-choice', 'short-answer' 유형 처리  ★★★★★
        # --------------------------------------------------------------------------
        elif content_type in ['multiple-choice', 'short-answer']:
            student_answer_str = request.POST.get('student_answer', '').strip()
            if not student_answer_str:
                return JsonResponse({'status': 'error', 'message': '답안이 입력되지 않았습니다.'}, status=400)

            correct_answer = parse_correct_answer(content.answer)
            is_correct = (student_answer_str == correct_answer)
            score = 100.0 if is_correct else 0.0
            
            answer_data = {
                'selected_answer': student_answer_str,
                'correct_answer': correct_answer,
            }

            student_answer_obj, created = StudentAnswer.objects.update_or_create(
                student=student,
                slide=slide,
                defaults={
                    'answer': answer_data,
                    'is_correct': is_correct,
                    'score': score,
                    'feedback': '자동 채점 완료',
                }
            )

            print(f"답안 {'생성' if created else '업데이트'} 완료: ID {student_answer_obj.id} (학생: {student.id}, 슬라이드: {slide.id})")
            # ★★★ 정답인 경우 StudentProgress 완료 처리 ★★★
            if is_correct and not progress.is_completed:
                progress.is_completed = True
                progress.completed_at = timezone.now()
                progress.save()

            response_data = {
                'status': 'success',
                'is_correct': is_correct,
                'correct_answer': correct_answer,
                'student_answer': student_answer_str,
                'score': student_answer_obj.score,
                'submitted_at': student_answer_obj.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                'feedback': student_answer_obj.feedback,
            }
            return JsonResponse(response_data)
            
        else:
            # 지원하지 않는 문제 유형 처리
            return JsonResponse({'status': 'error', 'message': f"지원하지 않는 문제 유형입니다: {content_type}"}, status=400)

    # 3. 모든 예외에 대한 공통 처리
    except ChasiSlide.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '요청한 슬라이드를 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        import traceback
        print(f"ERROR: check_answer 뷰에서 예외 발생: {str(e)}")
        print(f"트레이스백: {traceback.format_exc()}")
        return JsonResponse({
            'status': 'error',
            'message': f'서버 오류가 발생했습니다: {str(e)}',
        }, status=500)
    


# ★★★★★ [추가] one-shot-submit 유형 답안 제출을 처리하는 AJAX 뷰 ★★★★★
@login_required
@student_required
@require_POST
def submit_answer(request):
    """
    'one-shot-submit' 유형의 학생 답안을 저장하는 AJAX 뷰.
    제출 즉시 100점을 부여합니다.
    """
    try:
        # 1. 데이터 가져오기 및 유효성 검사
        slide_id = request.POST.get('slide_id')
        student_answer_text = request.POST.get('student_answer_text', '').strip()

        if not all([slide_id, student_answer_text]):
            return JsonResponse({
                'status': 'error',
                'message': '필수 데이터(slide_id, 답안)가 누락되었습니다.',
            }, status=400)

        # 2. 객체 조회
        student = request.user.student
        slide = get_object_or_404(
            ChasiSlide.objects.select_related('content', 'content_type'),
            id=slide_id
        )

        # 3. 콘텐츠 유형 확인 (one-shot-submit 유형인지 확인)
        if slide.content_type.type_name != 'one_shot_submit':
            return JsonResponse({
                'status': 'error',
                'message': f'잘못된 문제 유형({slide.content_type.type_name})에 대한 요청입니다.',
            }, status=400)
        
         # ★★★ StudentProgress 가져오기 또는 생성 ★★★
        progress, created = StudentProgress.objects.get_or_create(
            student=student,
            slide=slide,
            defaults={'started_at': timezone.now()}
        )
        
        # 4. DB에 저장할 데이터 구조 생성
        answer_data_to_save = {
            'submitted_text': student_answer_text,
        }

        # 5. DB에 저장 (update_or_create로 재제출 시에도 처리)
        # StudentAnswer 모델에 unique_together = ['student', 'slide'] 설정이 있으므로 이 방식이 안전합니다.
        student_answer_obj, created = StudentAnswer.objects.update_or_create(
            student=student,
            slide=slide,
            defaults={
                'answer': answer_data_to_save,
                'is_correct': True, # 제출 시 정답으로 처리
                'score': 100.0,      # 제출 시 100점 부여
                'feedback': 'one_shot_submit 형 제출완료',
            }
        )

        # ★★★ 제출 즉시 StudentProgress 완료 처리 ★★★
        if not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = timezone.now()
            progress.save()
        
        # 6. 클라이언트에 보낼 응답 데이터 구성
        response_data = {
            'status': 'success',
            'message': '답안이 성공적으로 제출되었습니다.',
            'submitted_text': student_answer_text,
            'score': student_answer_obj.score,
            'submitted_at': student_answer_obj.submitted_at.strftime('%Y-%m-%d %H:%M'),
        }
        return JsonResponse(response_data)

    except ChasiSlide.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '요청한 슬라이드를 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        import traceback
        print(f"ERROR: submit_answer 뷰에서 예외 발생: {str(e)}")
        print(f"트레이스백: {traceback.format_exc()}")
        return JsonResponse({
            'status': 'error',
            'message': f'서버 오류가 발생했습니다: {str(e)}',
        }, status=500)





# ★★★★★ [수정] physical_record 유형 제출 처리 View ★★★★★
@login_required
@student_required
@require_POST
def submit_physical_record(request):
    """
    'physical_record' 유형의 학생 실기 기록을 새로운 형식으로 저장하는 AJAX 뷰.
    """
    try:
        # 1. 데이터 가져오기 및 유효성 검사
        slide_id = request.POST.get('slide_id')
        attempt1_val = request.POST.get('attempt1_val', '').strip()
        attempt2_val = request.POST.get('attempt2_val', '').strip()

        if not all([slide_id, attempt1_val, attempt2_val]):
            return JsonResponse({'status': 'error', 'message': '모든 회차의 기록이 필요합니다.'}, status=400)

        student = request.user.student
        slide = get_object_or_404(ChasiSlide.objects.select_related('content__content_type'), id=slide_id)
        
         # ★★★ StudentProgress 가져오기 또는 생성 ★★★
        progress, created = StudentProgress.objects.get_or_create(
            student=student,
            slide=slide,
            defaults={'started_at': timezone.now()}
        )

        # 2. 시간(MM:SS.ms)을 밀리초(float)로 변환
        def convert_time_to_ms(time_str):
            try:
                parts = time_str.replace('.', ':').split(':')
                return float((int(parts[0]) * 60 + int(parts[1])) * 1000 + int(parts[2]) * 10)
            except (ValueError, IndexError): return None

        attempt1_ms = convert_time_to_ms(attempt1_val)
        attempt2_ms = convert_time_to_ms(attempt2_val)

        if attempt1_ms is None or attempt2_ms is None:
            return JsonResponse({'status': 'error', 'message': '잘못된 시간 형식입니다.'}, status=400)

        # 3. DB 저장을 하나의 트랜잭션으로 처리
        with transaction.atomic():
            # 3-1. 슬라이드 정보에서 측정 항목과 단위 조회
            slide_answer_data = json.loads(slide.content.answer or "{}")
            item_name = slide_answer_data.get('item', '기록') # 예: '달리기'
            
            try:
                # PhysicalResultType에서 종류와 단위 정보 가져오기
                result_type = PhysicalResultType.objects.get(type_name=item_name)
                unit = result_type.measure # 예: 'mili_second'
            except PhysicalResultType.DoesNotExist:
                # 해당 타입이 없으면 기본값 사용
                unit = 'mili_second'

            # 3-2. StudentAnswer 모델에 저장할 데이터 구성
            feedback_text = f"1차 시기: {attempt1_val}<br>2차 시기: {attempt2_val}"
            student_answer_obj, _ = StudentAnswer.objects.update_or_create(
                student=student, slide=slide,
                defaults={
                    'answer': {'item': item_name},
                    'is_correct': True, 'score': 100.0,
                    'feedback': feedback_text
                }
            )

            # 3-3. StudentPhysicalResult 모델에 저장할 JSON 리스트 생성
            record_list = [
                {"회차": 1, "기록": attempt1_ms, "단위": unit, "종류": item_name},
                {"회차": 2, "기록": attempt2_ms, "단위": unit, "종류": item_name}
            ]
            
            # StudentPhysicalResult.record 필드는 models.JSONField() 여야 합니다.
            physical_result_obj, _ = StudentPhysicalResult.objects.update_or_create(
                student=student, slide=slide,
                defaults={
                    'record': record_list,
                    'score': 100.0,
                    'writer': student.user.get_full_name()
                }
            )

            # ★★★ 기록 제출 시 StudentProgress 완료 처리 ★★★
            if not progress.is_completed:
                progress.is_completed = True
                progress.completed_at = timezone.now()
                progress.save()

        # 4. 클라이언트에 성공 응답 전송 (feedback 포함)
        return JsonResponse({
            'status': 'success',
            'message': '기록이 성공적으로 제출되었습니다.',
            'feedback': feedback_text
        })

    except Exception as e:
        import traceback
        return JsonResponse({'status': 'error', 'message': f'서버 오류: {traceback.format_exc()}'}, status=500)

# 밀리초를 시간(MM:SS.ms)으로 변환하는 헬퍼 함수 (응답 시 사용)
def format_ms_to_time(ms):
    total_seconds = ms / 1000
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    hundredths = int((ms % 1000) / 10)
    return f"{minutes:02d}:{seconds:02d}.{hundredths:02d}"


# ★★★★★ [수정] ordering 유형 답안 채점 View (로그 추가 및 로직 수정) ★★★★★
@login_required
@student_required
@require_POST
def check_ordering(request):
    """
    'ordering' 유형의 학생 답안을 채점하고 저장하는 AJAX 뷰.
    """
    try:
        # 1. 데이터 가져오기
        slide_id = request.POST.get('slide_id')
        user_order = request.POST.get('user_order', '').strip()

        if not all([slide_id, user_order]):
            return JsonResponse({'status': 'error', 'message': '필수 데이터가 누락되었습니다.'}, status=400)

        # 2. 객체 조회
        student = request.user.student
        slide = get_object_or_404(ChasiSlide.objects.select_related('content'), id=slide_id)
        
        # ★★★ StudentProgress 가져오기 또는 생성 ★★★
        progress, created = StudentProgress.objects.get_or_create(
            student=student,
            slide=slide,
            defaults={'started_at': timezone.now()}
        )

        # --- ★★★★★ 로그 추가 및 로직 수정 부분 시작 ★★★★★ ---

        # 로그 1: 클라이언트가 보낸 학생 답안 확인
        print(f"✅ User's Submitted Order: '{user_order}' (Type: {type(user_order)})")

        # 로그 2: 데이터베이스에서 가져온 원본 정답 데이터 확인

        raw_answer_from_db = slide.content.answer
        print(f"✅ Raw Answer from DB: '{raw_answer_from_db}' (Type: {type(raw_answer_from_db)})")
        
        # 3. JSON 문자열을 파싱하여 실제 정답 추출
        try:
            answer_data = json.loads(raw_answer_from_db)
            correct_answer = answer_data.get('answer', '').strip()
        except (json.JSONDecodeError, AttributeError):
            # JSON 형식이 아니거나 'answer' 키가 없는 경우에 대한 예외 처리
            correct_answer = raw_answer_from_db.strip()

        # 로그 3: 파싱 후 비교에 사용될 실제 정답 확인
        print(f"✅ Parsed Correct Answer: '{correct_answer}' (Type: {type(correct_answer)})")
        
        # 4. 정답 비교
        is_correct = (user_order == correct_answer)
        score = 100.0 if is_correct else 0.0

        # 로그 4: 최종 비교 결과 확인
        print(f"➡️ Comparing '{user_order}' == '{correct_answer}' -> Result: {is_correct}")
        
        # --- ★★★★★ 로그 추가 및 로직 수정 부분 끝 ★★★★★ ---
        
        # 5. DB에 학생 답안 저장
        with transaction.atomic():
            student_answer_obj, _ = StudentAnswer.objects.update_or_create(
                student=student,
                slide=slide,
                defaults={
                    'answer': {'submitted_order': user_order},
                    'is_correct': is_correct,
                    'score': score,
                    'feedback': '정답입니다!' if is_correct else '순서가 틀렸습니다. 다시 시도해 보세요.'
                }
            )

            # ★★★ 정답인 경우 StudentProgress 완료 처리 ★★★
            if is_correct and not progress.is_completed:
                progress.is_completed = True
                progress.completed_at = timezone.now()
                progress.save()
            
        # 6. 클라이언트에 채점 결과 응답
        return JsonResponse({
            'status': 'success',
            'is_correct': is_correct
        })

    except Exception as e:
        import traceback
        # ... 기존과 동일한 예외 처리 ...
        return JsonResponse({'status': 'error', 'message': f'서버 오류: {traceback.format_exc()}'}, status=500)
    

@login_required
@student_required
def save_note_ajax(request, slide_id):
    """노트 저장 AJAX 처리"""
    if request.method == 'POST':
        student = request.user.student
        slide = get_object_or_404(ChasiSlide, id=slide_id)
        
        note_content = request.POST.get('note_content', '')
        
        if note_content.strip():
            note, created = StudentNote.objects.update_or_create(
                student=student,
                slide=slide,
                defaults={'content': note_content}
            )
            return JsonResponse({'status': 'success'})
        else:
            # 빈 내용이면 노트 삭제
            StudentNote.objects.filter(student=student, slide=slide).delete()
            return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'})


from django.core.paginator import Paginator
from django.db.models import Prefetch

@login_required
@student_required
def my_answers_view(request):
    """내 답안 목록"""
    student = request.user.student
    
    # 기본 쿼리
    answers = StudentAnswer.objects.filter(
        student=student
    ).select_related(
        'slide__chasi__sub_chapter__chapter__subject',
        'slide__content_type',
        'slide__content'
    ).order_by('-submitted_at')
    
    # 코스 필터링
    course_id = request.GET.get('course')
    if course_id:
        answers = answers.filter(slide__chasi__sub_chapter__chapter__subject_id=course_id)
    
    # 차시 필터링 (새로 추가)
    chasi_id = request.GET.get('chasi')
    if chasi_id:
        answers = answers.filter(slide__chasi_id=chasi_id)
    
    # 검색 기능
    search_query = request.GET.get('search')
    if search_query:
        answers = answers.filter(
            Q(slide__content__title__icontains=search_query) |
            Q(slide__chasi__chasi_title__icontains=search_query)
        )
    
    # 정답 여부 필터
    correct_filter = request.GET.get('correct')
    if correct_filter == 'true':
        answers = answers.filter(is_correct=True)
    elif correct_filter == 'false':
        answers = answers.filter(is_correct=False)
    
    # 통계 계산 (필터링 후의 결과로)
    total_answers = answers.count()
    correct_answers = answers.filter(is_correct=True).count()
    incorrect_answers = answers.filter(is_correct=False).count()
    
    # 정답률 계산
    if total_answers > 0:
        correct_rate = int((correct_answers / total_answers) * 100)
    else:
        correct_rate = 0
    
    # 페이지네이션
    paginator = Paginator(answers, 20)  # 페이지당 20개
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # 코스 목록 (필터용)
    courses = Course.objects.filter(
        assignments__in=CourseAssignment.objects.filter(
            Q(assigned_class=student.school_class) | Q(assigned_student=student)
        )
    ).distinct()
    
    # 차시 목록 (선택된 코스가 있을 때만)
    chasis = []
    if course_id:
        chasis = Chasi.objects.filter(
            sub_chapter__chapter__subject_id=course_id,
            is_published=True
        ).select_related(
            'sub_chapter__chapter'
        ).order_by(
            'sub_chapter__chapter__chapter_order',
            'sub_chapter__sub_chapter_order',
            'chasi_order'
        )
    
    # 현재 필터 파라미터들을 유지하기 위한 딕셔너리
    filter_params = {}
    if course_id:
        filter_params['course'] = course_id
    if chasi_id:
        filter_params['chasi'] = chasi_id
    if correct_filter:
        filter_params['correct'] = correct_filter
    if search_query:
        filter_params['search'] = search_query
    
    context = {
        'page_obj': page_obj,
        'answers': page_obj,  # 템플릿 호환성을 위해 유지
        'courses': courses,
        'chasis': chasis,
        'selected_course_id': course_id,
        'selected_chasi_id': chasi_id,
        'total_answers': total_answers,
        'correct_answers': correct_answers,
        'incorrect_answers': incorrect_answers,
        'correct_rate': correct_rate,
        'filter_params': filter_params,
    }
    
    return render(request, 'student/my_answers.html', context)


@login_required
@student_required
def my_answers_view_0609(request):
    """내 답안 목록"""
    student = request.user.student
    
    # 기본 쿼리
    answers = StudentAnswer.objects.filter(
        student=student
    ).select_related(
        'slide__chasi__sub_chapter__chapter__subject',
        'slide__content_type'
    ).order_by('-submitted_at')
    
    # 필터링
    course_id = request.GET.get('course')
    if course_id:
        answers = answers.filter(slide__chasi__sub_chapter__chapter__subject_id=course_id)
    
    # 정답 여부 필터
    correct_filter = request.GET.get('correct')
    if correct_filter == 'true':
        answers = answers.filter(is_correct=True)
    elif correct_filter == 'false':
        answers = answers.filter(is_correct=False)
    
    # 통계 계산
    total_answers = answers.count()
    correct_answers = answers.filter(is_correct=True).count()
    incorrect_answers = answers.filter(is_correct=False).count()
    
    # 정답률 계산 (view에서 처리)
    if total_answers > 0:
        correct_rate = int((correct_answers / total_answers) * 100)
    else:
        correct_rate = 0
    
    # 코스 목록 - courseassignment를 assignments로 변경
    courses = Course.objects.filter(
        assignments__in=CourseAssignment.objects.filter(
            Q(assigned_class=student.school_class) | Q(assigned_student=student)
        )
    ).distinct()
    
    context = {
        'answers': answers,
        'courses': courses,
        'total_answers': total_answers,
        'correct_answers': correct_answers,
        'incorrect_answers': incorrect_answers,
        'correct_rate': correct_rate,  # 정답률 추가
    }
    
    return render(request, 'student/my_answers.html', context)

@login_required
@student_required
def my_answers_view_0608(request):
    """내 답안 목록"""
    student = request.user.student
    
    # 기본 쿼리
    answers = StudentAnswer.objects.filter(
        student=student
    ).select_related(
        'slide__chasi__sub_chapter__chapter__subject',
        'slide__content_type'
    ).order_by('-submitted_at')
    
    # 필터링
    course_id = request.GET.get('course')
    if course_id:
        answers = answers.filter(slide__chasi__sub_chapter__chapter__subject_id=course_id)
    
    # 정답 여부 필터
    correct_filter = request.GET.get('correct')
    if correct_filter == 'true':
        answers = answers.filter(is_correct=True)
    elif correct_filter == 'false':
        answers = answers.filter(is_correct=False)
    
    # 통계 계산
    total_answers = answers.count()
    correct_answers = answers.filter(is_correct=True).count()
    incorrect_answers = answers.filter(is_correct=False).count()
    
    # 코스 목록 - courseassignment를 assignments로 변경
    courses = Course.objects.filter(
        assignments__in=CourseAssignment.objects.filter(
            Q(assigned_class=student.school_class) | Q(assigned_student=student)
        )
    ).distinct()
    
    context = {
        'answers': answers,
        'courses': courses,
        'total_answers': total_answers,
        'correct_answers': correct_answers,
        'incorrect_answers': incorrect_answers,
    }
    
    return render(request, 'student/my_answers.html', context)

@login_required
@student_required
def course_progress_api(request, course_id):
    """코스 진도 API"""
    student = request.user.student
    course = get_object_or_404(Course, id=course_id)
    
    # 전체 슬라이드 수
    total_slides = ChasiSlide.objects.filter(
        chasi__sub_chapter__chapter__subject=course
    ).count()
    
    # 완료한 슬라이드 수
    completed_slides = StudentProgress.objects.filter(
        student=student,
        slide__chasi__sub_chapter__chapter__subject=course,
        is_completed=True
    ).count()
    
    progress_percent = 0
    if total_slides > 0:
        progress_percent = int((completed_slides / total_slides) * 100)
    
    return JsonResponse({
        'total_slides': total_slides,
        'completed_slides': completed_slides,
        'progress_percent': progress_percent,
    })