# teacher/statistics_views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Avg, Max, Min, Q, F
from django.utils import timezone
from django.http import JsonResponse
from datetime import datetime, timedelta
import json
from collections import defaultdict
from .decorators import teacher_required
from .models import Course, Chapter, SubChapter, Chasi, ChasiSlide, CourseAssignment
from accounts.models import Teacher, Class, Student
from student.models import StudentAnswer, StudentProgress, StudentPhysicalResult


@login_required
@teacher_required
def statistics_dashboard_view(request):
    """통계 대시보드 메인"""
    teacher = request.user.teacher
    
    # 기본 통계
    stats = {
        'total_classes': Class.objects.filter(teachers=teacher).count(),
        'total_students': Student.objects.filter(school_class__teachers=teacher).distinct().count(),
        'total_courses': Course.objects.filter(teacher=teacher).count(),
        'total_submissions': StudentAnswer.objects.filter(
            slide__chasi__subject__teacher=teacher
        ).count() if 'StudentAnswer' in globals() else 0,
    }
    
    # 최근 7일간 제출 추이
    week_ago = timezone.now() - timedelta(days=7)
    daily_submissions = []
    
    if 'StudentAnswer' in globals():
        for i in range(7):
            date = week_ago + timedelta(days=i)
            count = StudentAnswer.objects.filter(
                slide__chasi__subject__teacher=teacher,
                submitted_at__date=date.date()
            ).count()
            daily_submissions.append({
                'date': date.strftime('%m/%d'),
                'count': count
            })
    else:
        # 더미 데이터
        for i in range(7):
            date = week_ago + timedelta(days=i)
            daily_submissions.append({
                'date': date.strftime('%m/%d'),
                'count': 0
            })
    
    context = {
        'stats': stats,
        'daily_submissions': json.dumps(daily_submissions),
    }
    
    return render(request, 'teacher/statistics/dashboard.html', context)

@login_required
@teacher_required
def statistics_by_class_view(request):
    """반별 통계"""
    teacher = request.user.teacher
    classes = Class.objects.filter(teachers=teacher).order_by('name')
    
    selected_class_id = request.GET.get('class_id')
    selected_class = None
    class_stats = None
    student_stats = []
    
    if selected_class_id:
        try:
            selected_class = Class.objects.get(id=selected_class_id, teachers=teacher)
            
            # 반 전체 통계
            students = Student.objects.filter(school_class=selected_class)
            total_students = students.count()
            
            # 과제 제출률
            total_assignments = CourseAssignment.objects.filter(
                Q(assigned_class=selected_class) | Q(assigned_student__school_class=selected_class)
            ).distinct().count()
            
            completed_assignments = CourseAssignment.objects.filter(
                Q(assigned_class=selected_class) | Q(assigned_student__school_class=selected_class),
                is_completed=True
            ).distinct().count()
            
            # 평균 성취율
            avg_achievement = StudentAnswer.objects.filter(
                student__school_class=selected_class,
                is_correct=True
            ).aggregate(
                total=Count('id'),
                correct=Count('id', filter=Q(is_correct=True))
            )
            
            achievement_rate = 0
            if avg_achievement['total'] > 0:
                achievement_rate = (avg_achievement['correct'] / avg_achievement['total']) * 100
            
            class_stats = {
                'total_students': total_students,
                'total_assignments': total_assignments,
                'completed_assignments': completed_assignments,
                'completion_rate': (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0,
                'achievement_rate': round(achievement_rate, 1),
            }
            
            # 학생별 통계
            for student in students:
                student_answers = StudentAnswer.objects.filter(student=student)
                total_answers = student_answers.count()
                correct_answers = student_answers.filter(is_correct=True).count()
                
                student_stats.append({
                    'student': student,
                    'total_submissions': total_answers,
                    'correct_answers': correct_answers,
                    'accuracy_rate': round((correct_answers / total_answers * 100), 1) if total_answers > 0 else 0,
                    'last_activity': student_answers.order_by('-submitted_at').first().submitted_at if total_answers > 0 else None
                })
                
        except Class.DoesNotExist:
            pass
    
    context = {
        'classes': classes,
        'selected_class': selected_class,
        'class_stats': class_stats,
        'student_stats': student_stats,
    }
    
    return render(request, 'teacher/statistics/by_class.html', context)

@login_required
@teacher_required
def statistics_by_course_view(request):
    """코스별 통계"""
    teacher = request.user.teacher
    courses = Course.objects.filter(teacher=teacher).order_by('subject_name')
    
    selected_course_id = request.GET.get('course_id')
    selected_course = None
    course_stats = None
    chasi_stats = []
    
    if selected_course_id:
        try:
            selected_course = Course.objects.get(id=selected_course_id, teacher=teacher)
            
            # 코스 전체 통계
            total_chasis = Chasi.objects.filter(subject=selected_course).count()
            published_chasis = Chasi.objects.filter(subject=selected_course, is_published=True).count()
            
            # 학습 진도
            total_slides = ChasiSlide.objects.filter(chasi__subject=selected_course).count()
            viewed_slides = StudentAnswer.objects.filter(
                slide__chasi__subject=selected_course
            ).values('slide').distinct().count()
            
            course_stats = {
                'total_chasis': total_chasis,
                'published_chasis': published_chasis,
                'publish_rate': (published_chasis / total_chasis * 100) if total_chasis > 0 else 0,
                'total_slides': total_slides,
                'viewed_slides': viewed_slides,
                'progress_rate': (viewed_slides / total_slides * 100) if total_slides > 0 else 0,
            }
            
            # 차시별 통계
            chasis = Chasi.objects.filter(subject=selected_course).order_by('chasi_order')
            for chasi in chasis:
                slides = ChasiSlide.objects.filter(chasi=chasi)
                total_slide_count = slides.count()
                
                # 제출 통계
                submissions = StudentAnswer.objects.filter(slide__chasi=chasi)
                submission_count = submissions.count()
                correct_count = submissions.filter(is_correct=True).count()
                
                chasi_stats.append({
                    'chasi': chasi,
                    'slide_count': total_slide_count,
                    'submission_count': submission_count,
                    'correct_count': correct_count,
                    'accuracy_rate': round((correct_count / submission_count * 100), 1) if submission_count > 0 else 0,
                })
                
        except Course.DoesNotExist:
            pass
    
    context = {
        'courses': courses,
        'selected_course': selected_course,
        'course_stats': course_stats,
        'chasi_stats': chasi_stats,
    }
    
    return render(request, 'teacher/statistics/by_course.html', context)

@login_required
@teacher_required
def submission_analysis_view(request):
    """제출 답안 분석"""
    teacher = request.user.teacher
    
    # 필터 옵션
    filter_type = request.GET.get('filter', 'all')  # all, class, course, student
    filter_id = request.GET.get('filter_id')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # 기본 쿼리셋
    submissions = StudentAnswer.objects.filter(
        slide__chasi__subject__teacher=teacher
    ).select_related('student__user', 'student__school_class', 'slide__chasi__subject')
    
    # 필터 적용
    if filter_type == 'class' and filter_id:
        submissions = submissions.filter(student__school_class_id=filter_id)
    elif filter_type == 'course' and filter_id:
        submissions = submissions.filter(slide__chasi__subject_id=filter_id)
    elif filter_type == 'student' and filter_id:
        submissions = submissions.filter(student_id=filter_id)
    
    # 날짜 필터
    if date_from:
        submissions = submissions.filter(submitted_at__gte=date_from)
    if date_to:
        submissions = submissions.filter(submitted_at__lte=date_to)
    
    # 정렬
    submissions = submissions.order_by('-submitted_at')
    
    # 페이지네이션
    from django.core.paginator import Paginator
    paginator = Paginator(submissions, 50)
    page = request.GET.get('page')
    submissions_page = paginator.get_page(page)
    
    # 필터 옵션 목록
    classes = Class.objects.filter(teachers=teacher)
    courses = Course.objects.filter(teacher=teacher)
    students = Student.objects.filter(school_class__teachers=teacher).distinct()
    
    context = {
        'submissions': submissions_page,
        'filter_type': filter_type,
        'filter_id': filter_id,
        'classes': classes,
        'courses': courses,
        'students': students,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'teacher/statistics/submission_analysis.html', context)

@login_required
@teacher_required
def weakness_analysis_view(request):
    """취약점 및 강점 분석"""
    teacher = request.user.teacher
    
    analysis_type = request.GET.get('type', 'class')  # class, student
    target_id = request.GET.get('id')
    
    weakness_data = []
    strength_data = []
    frequent_errors = []
    
    if analysis_type == 'class' and target_id:
        try:
            target_class = Class.objects.get(id=target_id, teachers=teacher)
            
            # 콘텐츠 타입별 정답률 분석
            content_stats = StudentAnswer.objects.filter(
                student__school_class=target_class
            ).values('slide__content_type__type_name').annotate(
                total=Count('id'),
                correct=Count('id', filter=Q(is_correct=True))
            ).order_by('slide__content_type__type_name')
            
            for stat in content_stats:
                accuracy = (stat['correct'] / stat['total'] * 100) if stat['total'] > 0 else 0
                if accuracy < 60:
                    weakness_data.append({
                        'type': stat['slide__content_type__type_name'],
                        'accuracy': round(accuracy, 1),
                        'total': stat['total']
                    })
                elif accuracy > 80:
                    strength_data.append({
                        'type': stat['slide__content_type__type_name'],
                        'accuracy': round(accuracy, 1),
                        'total': stat['total']
                    })
            
            # 자주 틀리는 문제
            error_questions = StudentAnswer.objects.filter(
                student__school_class=target_class,
                is_correct=False
            ).values('slide__content__title', 'slide_id').annotate(
                error_count=Count('id')
            ).order_by('-error_count')[:10]
            
            frequent_errors = list(error_questions)
            
        except Class.DoesNotExist:
            pass
            
    elif analysis_type == 'student' and target_id:
        try:
            student = Student.objects.get(id=target_id, school_class__teachers=teacher)
            
            # 개인별 분석 로직
            # (위와 유사한 방식으로 구현)
            
        except Student.DoesNotExist:
            pass
    
    context = {
        'analysis_type': analysis_type,
        'weakness_data': weakness_data,
        'strength_data': strength_data,
        'frequent_errors': frequent_errors,
        'classes': Class.objects.filter(teachers=teacher),
        'students': Student.objects.filter(school_class__teachers=teacher).distinct(),
    }
    
    return render(request, 'teacher/statistics/weakness_analysis.html', context)

@login_required
@teacher_required
def physical_records_view_0609(request):
    """신체기록 통계 (수정된 버전)"""
    teacher = request.user.teacher
    
    filter_type = request.GET.get('filter', 'class')
    filter_id = request.GET.get('id')
    
    records_qs = StudentPhysicalResult.objects.none()
    target_object = None

    if filter_id:
        try:
            if filter_type == 'class':
                target_object = Class.objects.get(id=filter_id, teachers=teacher)
                records_qs = StudentPhysicalResult.objects.filter(student__school_class=target_object)
            elif filter_type == 'student':
                target_object = Student.objects.get(id=filter_id, school_class__teachers=teacher)
                records_qs = StudentPhysicalResult.objects.filter(student=target_object)
        except (Class.DoesNotExist, Student.DoesNotExist):
            messages.error(request, "요청한 학급 또는 학생을 찾을 수 없습니다.")
    
    records = records_qs.select_related('student__user').order_by('-submitted_at')

    # JSON 데이터 분석을 통한 통계 계산
    record_stats = defaultdict(list)
    if records:
        for record in records:
            # record 필드가 리스트 형태라고 가정
            if isinstance(record.record, list):
                for attempt in record.record:
                    record_type = attempt.get('종류')
                    record_value = attempt.get('기록')
                    # 기록 값이 숫자 형태일 경우만 통계에 포함
                    try:
                        record_stats[record_type].append(float(record_value))
                    except (ValueError, TypeError):
                        continue

    avg_stats = {
        record_type: round(sum(values) / len(values), 2)
        for record_type, values in record_stats.items() if values
    }
    
    context = {
        'records': records,
        'avg_stats': avg_stats,
        'filter_type': filter_type,
        'target_object': target_object,
        'classes': Class.objects.filter(teachers=teacher),
        'students': Student.objects.filter(school_class__teachers=teacher).distinct(),
    }
    
    return render(request, 'teacher/statistics/physical_records.html', context)

# statistics_views.py의 341번째 줄부터 시작하는 physical_records_view 함수를 다음으로 교체하세요:

@login_required
@teacher_required
def physical_records_view(request):
    """신체기록 통계"""
    teacher = request.user.teacher
    
    filter_type = request.GET.get('filter', 'class')
    filter_id = request.GET.get('id')
    
    records = []
    
    if filter_type == 'class' and filter_id:
        try:
            target_class = Class.objects.get(id=filter_id, teachers=teacher)
            # StudentPhysicalResult 모델 사용
            records = StudentPhysicalResult.objects.filter(
                student__school_class=target_class
            ).select_related('student__user').order_by('-submitted_at')
            
        except Class.DoesNotExist:
            pass
            
    elif filter_type == 'student' and filter_id:
        try:
            student = Student.objects.get(id=filter_id, school_class__teachers=teacher)
            # StudentPhysicalResult 모델 사용
            records = StudentPhysicalResult.objects.filter(
                student=student
            ).order_by('-submitted_at')
            
        except Student.DoesNotExist:
            pass
    
    # 평균 계산 - StudentPhysicalResult 모델에 맞게 수정
    if records:
        avg_stats = records.aggregate(
            avg_score=Avg('score'),
            total_count=Count('id')
        )
    else:
        avg_stats = None
    
    context = {
        'records': records,
        'avg_stats': avg_stats,
        'filter_type': filter_type,
        'filter_id': filter_id,
        'classes': Class.objects.filter(teachers=teacher),
        'students': Student.objects.filter(school_class__teachers=teacher).distinct(),
    }
    
    return render(request, 'teacher/statistics/physical_records.html', context)

# 참고: 이미 from student.models import StudentPhysicalResult가 파일 상단에 import되어 있으므로
# 추가 import는 필요하지 않습니다.

# API 엔드포인트들
@login_required
@teacher_required
def api_statistics_summary(request):
    """통계 요약 API"""
    teacher = request.user.teacher
    period = request.GET.get('period', 'week')  # week, month, all
    
    # 기간 설정
    if period == 'week':
        start_date = timezone.now() - timedelta(days=7)
    elif period == 'month':
        start_date = timezone.now() - timedelta(days=30)
    else:
        start_date = None
    
    # 기본 쿼리
    submissions = StudentAnswer.objects.filter(
        slide__chasi__subject__teacher=teacher
    )
    
    if start_date:
        submissions = submissions.filter(submitted_at__gte=start_date)
    
    # 통계 계산
    stats = {
        'total_submissions': submissions.count(),
        'unique_students': submissions.values('student').distinct().count(),
        'accuracy_rate': 0,
        'avg_time_spent': 0,
    }
    
    # 정답률
    if stats['total_submissions'] > 0:
        correct_count = submissions.filter(is_correct=True).count()
        stats['accuracy_rate'] = round((correct_count / stats['total_submissions']) * 100, 1)
    
    return JsonResponse(stats)

@login_required
@teacher_required
def export_statistics_view(request):
    """통계 데이터 내보내기"""
    import csv
    from django.http import HttpResponse
    
    teacher = request.user.teacher
    export_type = request.GET.get('type', 'summary')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="statistics_{export_type}_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    
    if export_type == 'submissions':
        # 제출 답안 내보내기
        writer.writerow(['학생명', '학번', '학급', '코스', '차시', '문제', '제출일시', '정답여부', '점수'])
        
        submissions = StudentAnswer.objects.filter(
            slide__chasi__subject__teacher=teacher
        ).select_related('student__user', 'student__school_class', 'slide__chasi__subject')
        
        for submission in submissions:
            writer.writerow([
                submission.student.user.get_full_name(),
                submission.student.student_id,
                submission.student.school_class.name,
                submission.slide.chasi.subject.subject_name,
                submission.slide.chasi.chasi_title,
                submission.slide.content.title,
                submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                '정답' if submission.is_correct else '오답',
                submission.score or 0
            ])
    
    return response