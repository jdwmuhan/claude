# views.py (전체)
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import models
from django.db.models import Sum, Count, Q, Avg
import json
from datetime import datetime

from .models import (
    HealthHabitTracker, DailyReflection, 
    DailyReflectionEvaluation, TrackerEvaluation
)
from accounts.models import Student, Teacher, Class
from teacher.models import ChasiSlide

# 학생용 뷰
@login_required
def student_health_habit_view(request, slide_id):
    """학생용 건강 습관 기록 페이지"""
    if not hasattr(request.user, 'student'):
        return JsonResponse({'error': '학생만 접근 가능합니다.'}, status=403)
    
    # 6가지 고정된 약속
    default_promises = {
        1: '바른 자세로 생활하기',
        2: '규칙적으로 가벼운 운동하기',
        3: '바른 식습관 기르기',
        4: '몸을 깨끗하게 하기',
        5: '생활 주변을 깨끗하게 하기',
        6: '마음 건강하게 관리하기'
    }
    
    # 약속 데이터 준비
    promises_list = []
    for i in range(1, 7):
        promises_list.append({
            'number': i,
            'placeholder': f'약속 {i}을 적어보세요!'
        })
    
    # 요일 데이터 준비
    week_days = [
        {'num': 1, 'name': '월'},
        {'num': 2, 'name': '화'},
        {'num': 3, 'name': '수'},
        {'num': 4, 'name': '목'},
        {'num': 5, 'name': '금'},
        {'num': 6, 'name': '토'},
        {'num': 7, 'name': '일'},
    ]
    
    context = {
        'slide_id': slide_id,
        'user': request.user,
        'promises_list': promises_list,
        'week_days': week_days,
    }
    return render(request, 'health_habit/student_health_habit.html', context)


@login_required
def get_tracker_data(request, slide_id):
    """트래커 데이터 조회"""
    try:
        student = request.user.student
        tracker, created = HealthHabitTracker.objects.get_or_create(
            student=student,
            slide_id=slide_id,
            defaults={'promises': {}}
        )
        
        # 리플렉션 데이터 포함
        reflections = []
        total_stars = 0
        
        for reflection in tracker.reflections.all():
            ref_data = {
                'promise_number': reflection.promise_number,
                'week': reflection.week,
                'day': reflection.day,
                'has_evaluation': hasattr(reflection, 'evaluation')
            }
            
            if hasattr(reflection, 'evaluation'):
                total_stars += reflection.evaluation.score
            
            reflections.append(ref_data)
        
        # 통계 계산
        stats = tracker.get_completion_stats()
        stats['total_stars'] = total_stars
        
        return JsonResponse({
            'success': True,
            'data': {
                'id': tracker.id,
                'promises': tracker.promises,
                'reflections': reflections,
                'statistics': stats,
                'is_submitted': tracker.is_submitted
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@login_required
def save_promises(request):
    """약속 저장"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            student = request.user.student
            slide_id = data.get('slide_id')
            promises = data.get('promises')
            
            tracker, _ = HealthHabitTracker.objects.get_or_create(
                student=student,
                slide_id=slide_id
            )
            
            tracker.promises = promises
            tracker.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@login_required
def save_reflection(request):
    """일일 소감 저장"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tracker_id = data.get('tracker_id')
            
            tracker = get_object_or_404(HealthHabitTracker, id=tracker_id)
            
            # 권한 확인
            if tracker.student != request.user.student:
                return JsonResponse({'error': '권한이 없습니다.'}, status=403)
            
            # DailyReflection 생성 또는 업데이트
            reflection, created = DailyReflection.objects.update_or_create(
                tracker=tracker,
                promise_number=data.get('promise_number'),
                week=data.get('week'),
                day=data.get('day'),
                defaults={
                    'reflection_text': data.get('reflection_text'),
                    'reflection_date': data.get('reflection_date'),
                    'reflection_time': data.get('reflection_time')
                }
            )
            
            return JsonResponse({
                'success': True,
                'created': created,
                'reflection_id': reflection.id
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def get_reflection(request, tracker_id, promise, week, day):
    """특정 소감 조회"""
    try:
        tracker = get_object_or_404(HealthHabitTracker, id=tracker_id)
        
        # 권한 확인
        if tracker.student != request.user.student:
            return JsonResponse({'error': '권한이 없습니다.'}, status=403)
        
        reflection = DailyReflection.objects.filter(
            tracker=tracker,
            promise_number=promise,
            week=week,
            day=day
        ).first()
        
        if reflection:
            return JsonResponse({
                'success': True,
                'data': {
                    'reflection_text': reflection.reflection_text,
                    'reflection_date': str(reflection.reflection_date),
                    'reflection_time': str(reflection.reflection_time)
                }
            })
        else:
            return JsonResponse({'success': True, 'data': None})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def get_promise_reflections(request, tracker_id, promise_num):
    """약속별 소감 목록"""
    try:
        tracker = get_object_or_404(HealthHabitTracker, id=tracker_id)
        
        # 권한 확인
        if tracker.student != request.user.student:
            return JsonResponse({'error': '권한이 없습니다.'}, status=403)
        
        reflections = DailyReflection.objects.filter(
            tracker=tracker,
            promise_number=promise_num
        ).order_by('week', 'day')
        
        days = ['월', '화', '수', '목', '금', '토', '일']
        
        data = []
        for ref in reflections:
            ref_data = {
                'id': ref.id,
                'week': ref.week,
                'day': ref.day,
                'day_name': days[ref.day - 1],
                'reflection_text': ref.reflection_text,
                'reflection_date': str(ref.reflection_date)
            }
            
            # 평가 정보 추가
            if hasattr(ref, 'evaluation'):
                ref_data['evaluation'] = {
                    'score': ref.evaluation.score,
                    'emoji': ref.evaluation.get_emoji_feedback_display(),
                    'comment': ref.evaluation.comment
                }
            
            data.append(ref_data)
        
        return JsonResponse({
            'success': True,
            'reflections': data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def get_final_reflection(request, tracker_id):
    """최종 소감 조회"""
    try:
        tracker = get_object_or_404(HealthHabitTracker, id=tracker_id)
        
        # 권한 확인
        is_teacher = hasattr(request.user, 'teacher')
        is_owner = hasattr(request.user, 'student') and tracker.student == request.user.student
        
        if not (is_teacher or is_owner):
            return JsonResponse({'error': '권한이 없습니다.'}, status=403)
        
        return JsonResponse({
            'success': True,
            'data': tracker.final_reflection
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@login_required
def submit_final(request):
    """최종 제출"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tracker_id = data.get('tracker_id')
            final_reflection = data.get('final_reflection')
            
            tracker = get_object_or_404(HealthHabitTracker, id=tracker_id)
            
            # 권한 확인
            if tracker.student != request.user.student:
                return JsonResponse({'error': '권한이 없습니다.'}, status=403)
            
            tracker.final_reflection = final_reflection
            tracker.is_submitted = True
            tracker.submitted_at = timezone.now()
            tracker.save()
            
            return JsonResponse({
                'success': True,
                'message': '제출이 완료되었습니다!'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


# 교사용 뷰
# views.py의 teacher_evaluation_view 수정
@login_required
def teacher_evaluation_view(request, slide_id):
    """교사용 평가 페이지"""
    if not hasattr(request.user, 'teacher'):
        return JsonResponse({'error': '교사만 접근 가능합니다.'}, status=403)
    
    teacher = request.user.teacher
    
    # 교사가 담당하는 학급 목록
    classes = teacher.classes.all()
    
    # 요일 데이터 준비
    week_days = [
        {'num': 1, 'name': '월'},
        {'num': 2, 'name': '화'},
        {'num': 3, 'name': '수'},
        {'num': 4, 'name': '목'},
        {'num': 5, 'name': '금'},
        {'num': 6, 'name': '토'},
        {'num': 7, 'name': '일'},
    ]
    
    context = {
        'slide_id': slide_id,
        'classes': classes,
        'user': request.user,
        'week_days': week_days,
    }
    return render(request, 'health_habit/teacher_evaluation.html', context)


@login_required
def get_students_for_evaluation(request, slide_id):
    """평가를 위한 학생 목록"""
    if not hasattr(request.user, 'teacher'):
        return JsonResponse({'error': '교사만 접근 가능합니다.'}, status=403)
    
    class_id = request.GET.get('class_id')
    
    # 쿼리 작성
    trackers = HealthHabitTracker.objects.filter(
        slide_id=slide_id,
        is_submitted=True
    ).select_related('student__user', 'student__school_class')
    
    if class_id:
        trackers = trackers.filter(student__school_class_id=class_id)
    
    students = []
    for tracker in trackers:
        stats = tracker.get_completion_stats()
        
        # 받은 별 개수 계산
        total_stars = DailyReflectionEvaluation.objects.filter(
            reflection__tracker=tracker
        ).aggregate(total=Sum('score'))['total'] or 0
        
        # 평가 여부
        is_evaluated = hasattr(tracker, 'overall_evaluation')
        
        students.append({
            'tracker_id': tracker.id,
            'name': tracker.student.user.get_full_name(),
            'student_grade': tracker.student.school_class.grade,
            'class_number': tracker.student.school_class.class_number,
            'number': tracker.student.student_id.split('_')[-1],
            'completion_rate': stats['completion_rate'],
            'total_reflections': stats['total_reflections'],
            'total_stars': total_stars,
            'is_evaluated': is_evaluated,
            'evaluation_grade': tracker.overall_evaluation.grade if is_evaluated else None
        })
    
    return JsonResponse({
        'success': True,
        'students': students
    })


@login_required
def get_student_detail_for_evaluation(request, tracker_id):
    """학생 상세 정보"""
    if not hasattr(request.user, 'teacher'):
        return JsonResponse({'error': '교사만 접근 가능합니다.'}, status=403)
    
    tracker = get_object_or_404(HealthHabitTracker, id=tracker_id)
    
    # 약속별 소감 정리
    promises = []
    for i in range(1, 7):
        reflections = DailyReflection.objects.filter(
            tracker=tracker,
            promise_number=i
        ).order_by('week', 'day')
        
        days = ['월', '화', '수', '목', '금', '토', '일']
        
        ref_list = []
        for ref in reflections:
            ref_data = {
                'id': ref.id,
                'week': ref.week,
                'day': ref.day,
                'day_name': days[ref.day - 1],
                'date': str(ref.reflection_date),
                'text': ref.reflection_text,
                'is_evaluated': hasattr(ref, 'evaluation')
            }
            
            if ref_data['is_evaluated']:
                ref_data['evaluation'] = {
                    'score': ref.evaluation.score,
                    'emoji': ref.evaluation.get_emoji_feedback_display(),
                    'comment': ref.evaluation.comment
                }
            
            ref_list.append(ref_data)
        
        promises.append({
            'number': i,
            'title': tracker.promises.get(str(i), f'약속 {i}'),
            'reflections': ref_list
        })
    
    # 기존 평가 정보
    overall_eval = None
    if hasattr(tracker, 'overall_evaluation'):
        overall_eval = {
            'grade': tracker.overall_evaluation.grade,
            'badges': tracker.overall_evaluation.badges,
            'feedback': tracker.overall_evaluation.feedback
        }
    
    return JsonResponse({
        'success': True,
        'data': {
            'student_name': tracker.student.user.get_full_name(),
            'promises': promises,
            'final_reflection': tracker.final_reflection,
            'overall_evaluation': overall_eval
        }
    })


@csrf_exempt
@login_required
def evaluate_reflection(request):
    """개별 소감 평가"""
    if request.method == 'POST':
        if not hasattr(request.user, 'teacher'):
            return JsonResponse({'error': '교사만 접근 가능합니다.'}, status=403)
        
        try:
            data = json.loads(request.body)
            reflection_id = data.get('reflection_id')
            
            reflection = get_object_or_404(DailyReflection, id=reflection_id)
            
            # 평가 생성 또는 업데이트
            evaluation, _ = DailyReflectionEvaluation.objects.update_or_create(
                reflection=reflection,
                defaults={
                    'teacher': request.user.teacher,
                    'score': data.get('score'),
                    'emoji_feedback': data.get('emoji_feedback'),
                    'comment': data.get('comment', ''),
                    'has_stamp': data.get('has_stamp', False)
                }
            )
            
            reflection.is_evaluated = True
            reflection.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@login_required
def save_overall_evaluation(request):
    """종합 평가 저장"""
    if request.method == 'POST':
        if not hasattr(request.user, 'teacher'):
            return JsonResponse({'error': '교사만 접근 가능합니다.'}, status=403)
        
        try:
            data = json.loads(request.body)
            tracker_id = data.get('tracker_id')
            
            tracker = get_object_or_404(HealthHabitTracker, id=tracker_id)
            
            # 총점 계산
            total_score = DailyReflectionEvaluation.objects.filter(
                reflection__tracker=tracker
            ).aggregate(total=Sum('score'))['total'] or 0
            
            # 평가 생성 또는 업데이트
            evaluation, _ = TrackerEvaluation.objects.update_or_create(
                tracker=tracker,
                defaults={
                    'teacher': request.user.teacher,
                    'grade': data.get('grade'),
                    'total_score': total_score,
                    'badges': data.get('badges', []),
                    'feedback': data.get('feedback')
                }
            )
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)