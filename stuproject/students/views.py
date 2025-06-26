from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from .models import (
    Student, Subject, StudentResult, StudentProfile, Fee, Department, 
    Course, StudentDepartmentCourse, Attendance, Enrollment, Lecture
)
from django.contrib.auth import authenticate, logout
from django.core.paginator import Paginator
from django.db.models import Q, F, Subquery, OuterRef  # Added Subquery and OuterRef
from datetime import datetime
from decimal import Decimal
import logging
from datetime import date
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.http import JsonResponse
# Configure logger
logger = logging.getLogger(__name__)

def superuser_required(user):
    return user.is_superuser

# Attendance Views
@login_required
@user_passes_test(superuser_required, login_url='login/')
def attendance_list(request):
    attendances = Attendance.objects.all().select_related('student', 'lecture__course').order_by('-lecture__date', '-lecture__time', 'student__id')
    lectures = Lecture.objects.all()

    # Apply GET filters
    lecture_id = request.GET.get('lecture')
    search_query = request.GET.get('search', '')

    if lecture_id:
        attendances = attendances.filter(lecture_id=lecture_id)
    if search_query:
        attendances = attendances.filter(
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student__roll_number__icontains=search_query)
        )

    paginator = Paginator(attendances, 5)  # 5 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'attendances': page_obj,
        'lectures': lectures,
        'search_query': search_query,
    }
    return render(request, 'students/attendance_list.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login/')
def get_lectures(request):
    course_id = request.GET.get('course_id')
    if not course_id:
        return JsonResponse({'error': 'Course ID is required'}, status=400)
    try:
        # Annotate subject_name to handle NULL subjects
        lectures = Lecture.objects.filter(course_id=course_id).annotate(
            subject_name=Subquery(
                Subject.objects.filter(id=OuterRef('subject_id')).values('name')[:1]
            )
        ).values('id', 'date', 'time', 'subject_name')
        logger.debug(f"Raw lectures data for course_id {course_id}: {list(lectures)}")
        lectures_data = [
            {
                'id': lecture['id'],
                'date': lecture['date'].isoformat() if lecture['date'] else '',
                'time': lecture['time'].strftime('%H:%M') if lecture['time'] else '09:00',
                'subject_name': lecture['subject_name'] if lecture['subject_name'] is not None else 'N/A'
            }
            for lecture in lectures
        ]
        logger.debug(f"Processed lectures data: {lectures_data}")
        return JsonResponse(lectures_data, safe=False)
    except Exception as e:
        logger.error(f"Error fetching lectures: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
    
    
@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login/')
def attendance_add(request):
    courses = Course.objects.all()
    form_data = {}
    students = []

    if request.method == 'POST':
        form_data = {
            'course_id': request.POST.get('course_id'),
            'lecture_id': request.POST.get('lecture_id'),
            'students': {key.replace('status_', ''): value for key, value in request.POST.items() if key.startswith('status_')}
        }
        try:
            if form_data['lecture_id']:
                lecture = get_object_or_404(Lecture, id=form_data['lecture_id'])
            else:
                # Create a new lecture if no lecture_id is provided
                course = get_object_or_404(Course, id=form_data['course_id'])
                lecture_date = datetime.strptime(request.POST.get('date'), '%Y-%m-%d').date()
                lecture_time = datetime.strptime(request.POST.get('time'), '%H:%M').time()
                current_datetime = timezone.now()
                if (lecture_date < current_datetime.date() or 
                    (lecture_date == current_datetime.date() and lecture_time < current_datetime.time())):
                    messages.error(request, 'Lecture date and time cannot be in the past.')
                    return render(request, 'students/attendance_add.html', {
                        'courses': courses,
                        'form_data': form_data,
                        'today': timezone.now().date().isoformat(),
                    })

                # Check for existing lecture with same date and time for the same course
                existing_lectures = Lecture.objects.filter(
                    course_id=form_data['course_id'],
                    date=lecture_date,
                    time=lecture_time
                ).exclude(subject__isnull=True).exists()
                if existing_lectures:
                    messages.error(request, 'There cannot be two subjects with the same date and time for the same course.')
                    return render(request, 'students/attendance_add.html', {
                        'courses': courses,
                        'form_data': form_data,
                        'today': timezone.now().date().isoformat(),
                    })

                lecture = Lecture.objects.create(course=course, date=lecture_date, time=lecture_time)
                form_data['lecture_id'] = lecture.id

            student_ids = list(form_data['students'].keys())
            students = Student.objects.filter(id__in=student_ids)

            with transaction.atomic():
                existing_attendances = Attendance.objects.filter(lecture=lecture, student__in=students).select_related('student')
                is_edit_mode = existing_attendances.exists()

                for student in students:
                    status = form_data['students'].get(str(student.id))
                    if not status:
                        continue
                    Attendance.objects.update_or_create(
                        lecture=lecture,
                        student=student,
                        defaults={'status': status}
                    )
                if is_edit_mode:
                    messages.success(request, 'Attendance updated successfully!')
                    logger.info(f"Attendance updated for lecture {lecture.id} by {request.user.username}")
                else:
                    messages.success(request, 'Attendance added successfully!')
                    logger.info(f"Attendance added for lecture {lecture.id} by {request.user.username}")
            return redirect('students:attendance_list')
        except ValueError as e:
            messages.error(request, f'Invalid date or time format: {str(e)}')
            logger.error(f"Invalid date/time format in attendance_add: {e}")
        except Exception as e:
            messages.error(request, f'Error adding/updating attendance: {str(e)}')
            logger.error(f"Error adding/updating attendance: {e}")
            students = Student.objects.filter(id__in=student_ids)

    elif request.method == 'GET' and 'lecture_id' in request.GET:
        lecture_id = request.GET.get('lecture_id')
        if lecture_id:
            lecture = get_object_or_404(Lecture, id=lecture_id)
            existing_attendances = Attendance.objects.filter(lecture=lecture).select_related('student')
            form_data['lecture_id'] = lecture_id
            form_data['date'] = lecture.date.isoformat()
            form_data['time'] = lecture.time.strftime('%H:%M')
            form_data['students'] = {str(a.student_id): a.status for a in existing_attendances}
            students = [a.student for a in existing_attendances]

    return render(request, 'students/attendance_add.html', {
        'courses': courses,
        'students': students,
        'form_data': form_data,
        'today': timezone.now().date().isoformat(),
    })
    

        
def get_lecture_students(request, lecture_id):
    try:
        lecture = get_object_or_404(Lecture, id=lecture_id)
        # Get students directly associated with the lecture via the ManyToManyField
        students = lecture.students.all().values('id', 'first_name', 'last_name', 'roll_number')
        return JsonResponse(list(students), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login/')
def attendance_edit(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id)
    students = [attendance.student]  # Limit to the current student
    courses = [attendance.lecture.course]  # Limit to the current course
    lectures = [attendance.lecture]  # Limit to the current lecture

    if request.method == 'POST':
        status = request.POST.get('status')
        if not status or status not in ['Present', 'Absent', 'Late']:
            messages.error(request, 'Please select a valid status (Present, Absent, or Late).')
            return render(request, 'students/attendance_edit.html', {
                'attendance': attendance,
                'students': students,
                'courses': courses,
                'lectures': lectures,
                'today': timezone.now().date().isoformat(),
            })

        try:
            with transaction.atomic():
                attendance.status = status
                attendance.save()
                messages.success(request, 'Attendance updated successfully!')
                logger.info(f"Attendance updated for attendance {attendance.id} by {request.user.username}")
            return redirect('students:attendance_list')
        except Exception as e:
            logger.error(f'Error updating attendance: {e}')
            messages.error(request, f'Error updating attendance: {e}')
            return render(request, 'students/attendance_edit.html', {
                'attendance': attendance,
                'students': students,
                'courses': courses,
                'lectures': lectures,
                'today': timezone.now().date().isoformat(),
            })

    context = {
        'attendance': attendance,
        'students': students,
        'courses': courses,
        'lectures': lectures,
        'today': timezone.now().date().isoformat(),
    }
    return render(request, 'students/attendance_edit.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def attendance_delete(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id)
    if request.method == 'POST':
        try:
            attendance.delete()
            messages.success(request, 'Attendance record deleted successfully!')
            return redirect('students:attendance_list')
        except Exception as e:
            logger.error(f'Error deleting attendance: {e}')
            messages.error(request, f'Error deleting attendance: {e}')
            return render(request, 'students/attendance_delete.html', {'attendance': attendance})
    return render(request, 'students/attendance_delete.html', {'attendance': attendance})
from django.http import JsonResponse


@login_required
@user_passes_test(superuser_required, login_url='login/')
def lectures_list(request):
    lectures = Lecture.objects.all().select_related('course', 'subject').order_by('-date')
    courses = Course.objects.all()
    subjects = Subject.objects.all()

    # Apply GET filters
    course_id = request.GET.get('course')
    subject_id = request.GET.get('subject')
    search_query = request.GET.get('search', '')

    if course_id:
        lectures = lectures.filter(course_id=course_id)
    if subject_id:
        lectures = lectures.filter(subject_id=subject_id)
    if search_query:
        lectures = lectures.filter(
            Q(course__name__icontains=search_query) |
            Q(subject__name__icontains=search_query)
        )

    paginator = Paginator(lectures, 5)  # 5 lectures per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'lectures': page_obj,
        'courses': courses,
        'subjects': subjects,
        'search_query': search_query,
    }
    return render(request, 'students/lectures_list.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def add_lecture(request):
    courses = Course.objects.all()
    subjects = Subject.objects.all()
    students = Student.objects.all().select_related('department_course__course')  # For validation errors
    today = datetime.now().date().strftime('%Y-%m-%d')

    if request.method == 'POST':
        logger.debug(f"POST data: {request.POST}")
        course_id = request.POST.get('course_id')
        subject_id = request.POST.get('subject_id')
        date = request.POST.get('date')
        time = request.POST.get('time')
        student_ids = request.POST.getlist('students')

        form_data = {
            'course_id': course_id,
            'subject_id': subject_id,
            'date': date,
            'time': time,
            'students': student_ids,
        }

        try:
            course = get_object_or_404(Course, id=course_id)
            subject = get_object_or_404(Subject, id=subject_id) if subject_id else None
            lecture_date = datetime.strptime(date, '%Y-%m-%d').date()
            lecture_time = datetime.strptime(time, '%H:%M').time()
            current_datetime = timezone.now()
            if (lecture_date < current_datetime.date() or 
                (lecture_date == current_datetime.date() and lecture_time < current_datetime.time())):
                messages.error(request, 'Lecture date and time cannot be in the past.')
                return render(request, 'students/add_lecture.html', {
                    'courses': courses,
                    'subjects': subjects,
                    'students': students,
                    'form_data': form_data,
                    'today': today,
                })

            # Check for existing lecture with same date and time for the same course
            existing_lectures = Lecture.objects.filter(
                course_id=course_id,
                date=lecture_date,
                time=lecture_time
            ).exclude(subject__isnull=True).exists()
            if existing_lectures:
                messages.error(request, 'There cannot be two subjects with the same date and time for the same course.')
                return render(request, 'students/add_lecture.html', {
                    'courses': courses,
                    'subjects': subjects,
                    'students': students,
                    'form_data': form_data,
                    'today': today,
                })

            # Create lecture
            lecture = Lecture.objects.create(
                course=course,
                subject=subject,
                date=lecture_date,
                time=lecture_time
            )
            # Add selected students
            if student_ids:
                selected_students = Student.objects.filter(
                    id__in=student_ids,
                    enrollment__course=course
                )
                lecture.students.set(selected_students)
                logger.debug(f"Added {selected_students.count()} students to lecture {lecture.id}")
            else:
                logger.debug("No students selected for lecture")

            messages.success(request, 'Lecture added successfully!')
            logger.info(f"Lecture for {course.name} on {lecture_date} at {lecture_time} added by {request.user.username}")
            return redirect('students:lectures_list')

        except ValueError as e:
            logger.error(f"Error adding lecture: {e}")
            messages.error(request, 'Invalid date or time format or input.')
            return render(request, 'students/add_lecture.html', {
                'courses': courses,
                'subjects': subjects,
                'students': students,
                'form_data': form_data,
                'today': today,
            })
        except Exception as e:
            logger.error(f"Error adding lecture: {e}")
            messages.error(request, f'Error adding lecture: {str(e)}')
            return render(request, 'students/add_lecture.html', {
                'courses': courses,
                'subjects': subjects,
                'students': students,
                'form_data': form_data,
                'today': today,
            })

    context = {
        'courses': courses,
        'subjects': subjects,
        'students': students,
        'form_data': {},
        'today': today,
    }
    return render(request, 'students/add_lecture.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def get_students_by_course(request):
    course_id = request.GET.get('course_id')
    logger.debug(f"Fetching students for course_id: {course_id}")

    if not course_id:
        logger.warning("No course_id provided in request")
        return JsonResponse({'error': 'Course ID required'}, status=400)

    try:
        course = Course.objects.get(id=course_id)
        students = Student.objects.filter(
            enrollment__course_id=course_id
        ).select_related('department_course__course', 'department_course__department').values(
            'id', 'first_name', 'last_name', 'roll_number'
        )
        student_list = list(students)
        logger.debug(f"Found {len(student_list)} students via Enrollment for course {course_id}")

        if not student_list:
            students = Student.objects.filter(
                department_course__course_id=course_id
            ).select_related('department_course__course', 'department_course__department').values(
                'id', 'first_name', 'last_name', 'roll_number'
            )
            student_list = list(students)
            logger.debug(f"Found {len(student_list)} students via StudentDepartmentCourse for course {course_id}")

        return JsonResponse(student_list, safe=False)
    except Course.DoesNotExist:
        logger.error(f"Course {course_id} does not exist")
        return JsonResponse({'error': 'Invalid course ID'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching students for course {course_id}: {str(e)}")
        return JsonResponse({'error': f'Error fetching students: {str(e)}'}, status=500)
    
@login_required
@user_passes_test(superuser_required, login_url='login/')
def enrollment_add(request):
    courses = Course.objects.all()
    students = Student.objects.all().select_related('department_course__course', 'department_course__department')
    form_data = {}

    if request.method == 'POST':
        logger.debug(f"POST data: {request.POST}")
        course_id = request.POST.get('course_id')
        student_ids = request.POST.getlist('students')

        form_data = {
            'course_id': course_id,
            'students': student_ids,
        }

        try:
            course = get_object_or_404(Course, id=course_id)
            department = course.department

            # Validate students
            if not student_ids:
                messages.error(request, 'Please select at least one student.')
                return render(request, 'students/enrollment_add.html', {
                    'courses': courses,
                    'students': students,
                    'form_data': form_data,
                })

            # Create enrollments
            enrolled_count = 0
            with transaction.atomic():
                for student_id in student_ids:
                    student = get_object_or_404(Student, id=student_id)
                    # Check if already enrolled
                    if not Enrollment.objects.filter(student=student, course=course).exists():
                        Enrollment.objects.create(student=student, course=course)
                        # Create StudentDepartmentCourse if not exists
                        StudentDepartmentCourse.objects.get_or_create(
                            student=student,
                            department=department,
                            course=course
                        )
                        enrolled_count += 1

            if enrolled_count > 0:
                messages.success(request, f'Successfully enrolled {enrolled_count} student(s).')
                logger.info(f"Enrolled {enrolled_count} students in course {course.id} by {request.user.username}")
                return redirect('students:enrollment_list')
            else:
                messages.info(request, 'No new students were enrolled (already enrolled).')
                return redirect('students:enrollment_list')

        except Exception as e:
            logger.error(f"Error adding enrollment: {e}")
            messages.error(request, f'Error enrolling students: {str(e)}')
            return render(request, 'students/enrollment_add.html', {
                'courses': courses,
                'students': students,
                'form_data': form_data,
            })

    context = {
        'courses': courses,
        'students': students,
        'form_data': {},
    }
    return render(request, 'students/enrollment_add.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def get_students_not_enrolled(request):
    course_id = request.GET.get('course_id')
    logger.debug(f"Fetching non-enrolled students for course_id: {course_id}")

    if not course_id:
        logger.warning("No course_id provided in request")
        return JsonResponse({'error': 'Course ID required'}, status=400)

    try:
        course = Course.objects.get(id=course_id)
        # Get students not enrolled in the course
        enrolled_student_ids = Enrollment.objects.filter(course_id=course_id).values_list('student_id', flat=True)
        students = Student.objects.exclude(
            id__in=enrolled_student_ids
        ).select_related('department_course__course', 'department_course__department').values(
            'id', 'first_name', 'last_name', 'roll_number'
        )
        student_list = list(students)
        logger.debug(f"Found {len(student_list)} non-enrolled students for course {course_id}")
        return JsonResponse(student_list, safe=False)
    except Course.DoesNotExist:
        logger.error(f"Course {course_id} does not exist")
        return JsonResponse({'error': 'Invalid course ID'}, status=404)
    except Exception as e:
        logger.error(f"Error fetching non-enrolled students for course {course_id}: {str(e)}")
        return JsonResponse({'error': f'Error fetching students: {str(e)}'}, status=500)
    
@login_required
@user_passes_test(superuser_required, login_url='login/')
def enrollment_list(request):
    enrollments = Enrollment.objects.all().select_related('student', 'course')
    context = {'enrollments': enrollments}
    return render(request, 'students/enrollment_list.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def edit_lecture(request, lecture_id):
    lecture = get_object_or_404(Lecture, id=lecture_id)
    courses = Course.objects.all()
    subjects = Subject.objects.all()
    students = Student.objects.filter(enrollment__course=lecture.course).select_related('department_course__course', 'department_course__department')
    today = datetime.now().date().strftime('%Y-%m-%d')

    if request.method == 'POST':
        logger.debug(f"POST data: {request.POST}")
        course_id = request.POST.get('course_id')
        subject_id = request.POST.get('subject_id')
        date = request.POST.get('date')
        time = request.POST.get('time')
        student_ids = request.POST.getlist('students')

        form_data = {
            'course_id': course_id,
            'subject_id': subject_id,
            'date': date,
            'time': time,
            'students': student_ids,
        }

        try:
            course = get_object_or_404(Course, id=course_id)
            subject = get_object_or_404(Subject, id=subject_id) if subject_id else None
            lecture_date = datetime.strptime(date, '%Y-%m-%d').date()
            lecture_time = datetime.strptime(time, '%H:%M').time()
            current_datetime = timezone.now()
            if (lecture_date < current_datetime.date() or 
                (lecture_date == current_datetime.date() and lecture_time < current_datetime.time())):
                messages.error(request, 'Lecture date and time cannot be in the past.')
                return render(request, 'students/edit_lecture.html', {
                    'lecture': lecture,
                    'courses': courses,
                    'subjects': subjects,
                    'students': students,
                    'form_data': form_data,
                    'today': today,
                })

            # Check for existing lecture with same date and time for the same course, excluding the current lecture
            existing_lectures = Lecture.objects.filter(
                course_id=course_id,
                date=lecture_date,
                time=lecture_time
            ).exclude(id=lecture_id).exclude(subject__isnull=True).exists()
            if existing_lectures:
                messages.error(request, 'There cannot be two subjects with the same date and time for the same course.')
                return render(request, 'students/edit_lecture.html', {
                    'lecture': lecture,
                    'courses': courses,
                    'subjects': subjects,
                    'students': students,
                    'form_data': form_data,
                    'today': today,
                })

            # Update lecture
            lecture.course = course
            lecture.subject = subject
            lecture.date = lecture_date
            lecture.time = lecture_time
            lecture.save()

            # Update students
            if student_ids:
                selected_students = Student.objects.filter(
                    id__in=student_ids,
                    enrollment__course=course
                )
                lecture.students.set(selected_students)
                logger.debug(f"Updated {selected_students.count()} students for lecture {lecture.id}")
            else:
                lecture.students.clear()
                logger.debug("No students selected for lecture")

            messages.success(request, 'Lecture updated successfully!')
            logger.info(f"Lecture {lecture.id} updated by {request.user.username}")
            return redirect('students:lectures_list')

        except ValueError as e:
            logger.error(f"Error updating lecture: {e}")
            messages.error(request, 'Invalid date or time format or input.')
            return render(request, 'students/edit_lecture.html', {
                'lecture': lecture,
                'courses': courses,
                'subjects': subjects,
                'students': students,
                'form_data': form_data,
                'today': today,
            })
        except Exception as e:
            logger.error(f"Error updating lecture: {e}")
            messages.error(request, f'Error updating lecture: {str(e)}')
            return render(request, 'students/edit_lecture.html', {
                'lecture': lecture,
                'courses': courses,
                'subjects': subjects,
                'students': students,
                'form_data': form_data,
                'today': today,
            })

    context = {
        'lecture': lecture,
        'courses': courses,
        'subjects': subjects,
        'students': students,
        'form_data': {
            'course_id': lecture.course.id,
            'subject_id': lecture.subject.id if lecture.subject else '',
            'date': lecture.date.isoformat(),
            'time': lecture.time.strftime('%H:%M'),
            'students': [str(s.id) for s in lecture.students.all()],
        },
        'today': today,
    }
    return render(request, 'students/edit_lecture.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def delete_lecture(request, lecture_id):
    lecture = get_object_or_404(Lecture, id=lecture_id)
    if request.method == 'POST':
        try:
            lecture.delete()
            messages.success(request, 'Lecture deleted successfully!')
            return redirect('students:lectures_list')
        except Exception as e:
            logger.error(f"Error deleting lecture: {e}")
            messages.error(request, f'Error deleting lecture: {e}')
            return render(request, 'students/delete_lecture.html', {'lecture': lecture})
    return render(request, 'students/delete_lecture.html', {'lecture': lecture})

# Updated Non-Superuser Views


@login_required
def student_detail(request, student_id):
    if request.user.is_superuser:
        student = get_object_or_404(Student, id=student_id)
        results = StudentResult.objects.filter(student=student)
    else:
        try:
            profile = StudentProfile.objects.get(user=request.user)
            student = profile.student
            if student.id != student_id:
                messages.error(request, "You are not authorized to view this student's details.")
                return redirect('students:profile')
            results = StudentResult.objects.filter(student=student)
        except StudentProfile.DoesNotExist:
            messages.error(request, "No student profile found for your account.")
            return redirect('students:student_list')

    # Get filter parameters
    selected_semester_ids = request.GET.getlist('semesters')
    selected_subject_ids = request.GET.getlist('subjects')
    selected_attendance_course_ids = request.GET.getlist('attendance_courses')
    attendance_start_date = request.GET.get('attendance_start_date')
    attendance_end_date = request.GET.get('attendance_end_date')
    
    # Get all semesters, subjects, and courses for the student
    all_semesters = StudentResult.objects.filter(student=student).values_list('semester', flat=True).distinct().order_by('semester')
    all_subjects = Subject.objects.filter(studentresult__student=student).distinct()
    all_attendance_courses = Course.objects.filter(lecture__attendance__student=student).distinct()
    logger.info("Fetching all_attendance_courses: %s", all_attendance_courses.query)

    # Filter results by semesters and subjects
    if selected_semester_ids or selected_subject_ids:
        query = Q()
        if selected_semester_ids:
            query &= Q(semester__in=selected_semester_ids)
        if selected_subject_ids:
            query &= Q(subject__in=selected_subject_ids)
        results = results.filter(query).order_by('semester', 'subject__name')
        semesters_to_display = selected_semester_ids if selected_semester_ids else all_semesters
    else:
        semesters_to_display = all_semesters

    # Prepare semester-wise data
    semester_data = []
    for semester in semesters_to_display:
        semester_results = results.filter(semester=semester)
        if semester_results.exists():
            grades = [result.grade for result in semester_results if result.grade]
            grade_counts = {grade: grades.count(grade) for grade in set(grades) if grade}
            grade_pairs = sorted([(grade, count) for grade, count in grade_counts.items()], key=lambda x: x[0])
            semester_data.append({
                'semester': semester,
                'results': semester_results,
                'grade_data': {
                    'labels': list(grade_counts.keys()),
                    'data': list(grade_counts.values()),
                },
                'grade_pairs': grade_pairs,
            })

    # Get attendance records with course and date filter
    attendance_query = Attendance.objects.filter(student=student).order_by('-lecture__date')
    if selected_attendance_course_ids:
        attendance_query = attendance_query.filter(lecture__course__in=selected_attendance_course_ids)
    if attendance_start_date:
        attendance_query = attendance_query.filter(lecture__date__gte=attendance_start_date)
    if attendance_end_date:
        attendance_query = attendance_query.filter(lecture__date__lte=attendance_end_date)
    attendances = attendance_query.select_related('lecture__course', 'lecture__subject')

    # Get student's fees
    fees = Fee.objects.filter(student=student).order_by('due_date')

    # Get the student's department and course
    try:
        student_dept_course = student.department_course
    except StudentDepartmentCourse.DoesNotExist:
        student_dept_course = None
        logger.debug(f"No department/course assignment found for student ID {student_id}")

    # Paginate results
    paginator = Paginator(results, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'student': student,
        'results': page_obj,
        'grade_data': {'labels': [], 'data': []},
        'student_dept_course': student_dept_course,
        'all_semesters': all_semesters,
        'selected_semester_ids': selected_semester_ids,
        'all_subjects': all_subjects,
        'selected_subject_ids': selected_subject_ids,
        'semester_data': semester_data,
        'all_attendance_courses': all_attendance_courses,
        'selected_attendance_course_ids': selected_attendance_course_ids,
        'selected_attendance_start_date': attendance_start_date,
        'selected_attendance_end_date': attendance_end_date,
        'attendances': attendances,
        'fees': fees,
    }
    return render(request, 'students/student_detail.html', context)


# ... (Other views remain unchanged)
# Unchanged Non-Attendance and Non-Classroom Views
@login_required
@user_passes_test(superuser_required, login_url='login/')
def edit_fee(request, fee_id):
    fee = get_object_or_404(Fee, id=fee_id)
    students = Student.objects.all()
    if request.method == 'POST':
        student_id = request.POST.get('student')
        amount = request.POST.get('amount')
        due_date = request.POST.get('due_date')
        is_paid = 'is_paid' in request.POST

        # Validate inputs
        try:
            student = get_object_or_404(Student, id=student_id)
        except ValueError:
            messages.error(request, 'Please select a valid student.')
            return render(request, 'students/edit_fee.html', {'fee': fee, 'students': students})

        try:
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be greater than zero.')
                return render(request, 'students/edit_fee.html', {'fee': fee, 'students': students})
        except (ValueError, TypeError, Decimal.InvalidOperation):
            messages.error(request, 'Invalid amount. Please enter a valid number.')
            return render(request, 'students/edit_fee.html', {'fee': fee, 'students': students})

        try:
            due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            if due_date < datetime(2025, 6, 6).date():
                messages.warning(request, 'The due date is in the past. Please confirm this is correct.')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid due date. Please use the format YYYY-MM-DD.')
            return render(request, 'students/edit_fee.html', {'fee': fee, 'students': students})

        # Update the fee
        try:
            fee.student = student
            fee.amount = amount
            fee.due_date = due_date
            fee.is_paid = is_paid
            fee.save()
            messages.success(request, 'Fee updated successfully!')
            return redirect('students:fees_list')
        except Exception as e:
            messages.error(request, f'Error updating fee: {e}')
            return render(request, 'students/edit_fee.html', {'fee': fee, 'students': students})

    context = {'fee': fee, 'students': students}
    return render(request, 'students/edit_fee.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def delete_fee(request, fee_id):
    fee = get_object_or_404(Fee, id=fee_id)
    fee.delete()
    messages.success(request, 'Fee deleted successfully!')
    return redirect('students:fees_list')

@login_required
def student_list(request):
    if request.user.is_superuser:
        students = Student.objects.all().order_by('id')
        search_query = request.GET.get('search', '')

        if search_query:
            students = students.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(roll_number__icontains=search_query)
            )

        # Pagination (5 students per page to match results_list)
        paginator = Paginator(students, 5)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Fetch student department/course assignments for the current page
        student_ids = [student.id for student in page_obj]
        student_dept_courses = StudentDepartmentCourse.objects.filter(student__id__in=student_ids).select_related('student', 'department', 'course')

        # Enhanced debugging
        print("Paginated Student IDs:", student_ids)
        print("Student Dept Courses Queryset:", list(student_dept_courses.values('student_id', 'department__name', 'course__name')))

        # Prepare grade distribution data for paginated students
        student_grade_data = []
        for student in page_obj:
            student_results = StudentResult.objects.filter(student=student)
            if student_results.exists():
                grades = [result.grade for result in student_results if result.grade]
                grade_counts = {grade: grades.count(grade) for grade in set(grades) if grade}
                grade_pairs = sorted([(grade, count) for grade, count in grade_counts.items()])
                
                student_grade_data.append({
                    'student_id': student.id,
                    'grade_data': {
                        'labels': list(grade_counts.keys()),
                        'data': list(grade_counts.values()),
                    },
                    'grade_pairs': grade_pairs
                })

        context = {
            'students': page_obj,
            'search_query': search_query,
            'student_grade_data': student_grade_data,
            'student_dept_courses': student_dept_courses,
        }
        return render(request, 'students/student_list.html', context)
    else:
        try:
            profile = StudentProfile.objects.get(user=request.user)
            return redirect('students:profile')
        except StudentProfile.DoesNotExist:
            messages.error(request, 'No student profile found for your account.')
            return redirect('students:student_list')

@login_required
@user_passes_test(superuser_required, login_url='login/')
def fees_list(request):
    fees = Fee.objects.all().select_related('student').order_by('student__id')
    students = Student.objects.all()
    search_query = request.GET.get('search', '')
    student_filter = request.GET.get('student', '')

    # Apply filters
    if search_query:
        fees = fees.filter(
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student__roll_number__icontains=search_query)
        )
    if student_filter:
        fees = fees.filter(student__id=student_filter)

    paginator = Paginator(fees, 5)  # 5 fees per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'fees': page_obj,
        'students': students,
        'search_query': search_query,
        'selected_student': student_filter,
    }
    return render(request, 'students/fees_list.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def add_fee(request):
    students = Student.objects.all()
    if request.method == 'POST':
        student_id = request.POST.get('student')
        amount = request.POST.get('amount')
        due_date = request.POST.get('due_date')
        is_paid = 'is_paid' in request.POST

        # Validate inputs
        try:
            student = get_object_or_404(Student, id=student_id)
        except ValueError:
            messages.error(request, 'Please select a valid student.')
            return render(request, 'students/add_fee.html', {'students': students})

        try:
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, 'Amount must be greater than zero.')
                return render(request, 'students/add_fee.html', {'students': students})
        except (ValueError, TypeError, Decimal.InvalidOperation):
            messages.error(request, 'Invalid amount. Please enter a valid number.')
            return render(request, 'students/add_fee.html', {'students': students})

        try:
            due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            if due_date < datetime(2025, 6, 6).date():
                messages.warning(request, 'The due date is in the past. Please confirm this is correct.')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid due date. Please use the format YYYY-MM-DD.')
            return render(request, 'students/add_fee.html', {'students': students})

        # Create the fee
        try:
            Fee.objects.create(
                student=student,
                amount=amount,
                due_date=due_date,
                is_paid=is_paid
            )
            messages.success(request, 'Fee added successfully!')
            return redirect('students:fees_list')
        except Exception as e:
            messages.error(request, f'Error adding fee: {e}')
            return render(request, 'students/add_fee.html', {'students': students})

    context = {'students': students}
    return render(request, 'students/add_fee.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def departments_list(request):
    departments = Department.objects.all()
    search_query = request.GET.get('search', '')

    if search_query:
        departments = departments.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query)
        )

    paginator = Paginator(departments, 5)  # 5 departments per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'departments': page_obj,
        'search_query': search_query,
    }
    return render(request, 'students/departments_list.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def add_department(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')

        # Validate inputs
        if not name or not code:
            messages.error(request, 'Both name and code are required.')
            return render(request, 'students/add_department.html')

        if Department.objects.filter(code=code).exists():
            messages.error(request, 'A department with this code already exists.')
            return render(request, 'students/add_department.html')

        try:
            Department.objects.create(name=name, code=code)
            messages.success(request, 'Department added successfully!')
            return redirect('students:departments_list')
        except Exception as e:
            messages.error(request, f'Error adding department: {e}')
            return render(request, 'students/add_department.html')

    return render(request, 'students/add_department.html')

@login_required
@user_passes_test(superuser_required, login_url='login/')
def edit_department(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    if request.method == 'POST':
        name = request.POST.get('name').strip()
        code = request.POST.get('code').strip()

        # Validate inputs
        if not name or not code:
            messages.error(request, 'Both name and code are required.')
            return render(request, 'students/edit_department.html', {'department': department})

        if Department.objects.filter(code=code).exclude(id=department.id).exists():
            messages.error(request, 'A department with this code already exists.')
            return render(request, 'students/edit_department.html', {'department': department})

        try:
            department.name = name
            department.code = code
            department.save()
            messages.success(request, 'Department updated successfully!')
            return redirect('students:departments_list')
        except Exception as e:
            messages.error(request, f'Error updating department: {e}')
            return render(request, 'students/edit_department.html', {'department': department})

    context = {'department': department}
    return render(request, 'students/edit_department.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def delete_department(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    department.delete()
    messages.success(request, 'Department deleted successfully!')
    return redirect('students:departments_list')

@login_required
@user_passes_test(superuser_required, login_url='login/')
def courses_list(request):
    courses = Course.objects.all().select_related('department')
    search_query = request.GET.get('search', '')
    department_filter = request.GET.get('department', '')

    if search_query:
        courses = courses.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query)
        )
    if department_filter:
        courses = courses.filter(department__id=department_filter)

    departments = Department.objects.all()
    paginator = Paginator(courses, 5)  # 5 courses per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'courses': page_obj,
        'departments': departments,
        'search_query': search_query,
        'selected_department': department_filter,
    }
    return render(request, 'students/courses_list.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def add_course(request):
    departments = Department.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        department_id = request.POST.get('department')

        # Validate inputs
        if not name or not code or not department_id:
            messages.error(request, 'Name, code, and department are required.')
            return render(request, 'students/add_course.html', {'departments': departments})

        if Course.objects.filter(code=code).exists():
            messages.error(request, 'A course with this code already exists.')
            return render(request, 'students/add_course.html', {'departments': departments})

        try:
            department = get_object_or_404(Department, id=department_id)
            Course.objects.create(name=name, code=code, department=department)
            messages.success(request, 'Course added successfully!')
            return redirect('students:courses_list')
        except Exception as e:
            messages.error(request, f'Error adding course: {e}')
            return render(request, 'students/add_course.html', {'departments': departments})

    context = {'departments': departments}
    return render(request, 'students/add_course.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def edit_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    departments = Department.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name').strip()
        code = request.POST.get('code').strip()
        department_id = request.POST.get('department')

        # Validate inputs
        if not name or not code or not department_id:
            messages.error(request, 'Name, code, and department are required.')
            return render(request, 'students/edit_course.html', {'course': course, 'departments': departments})

        if Course.objects.filter(code=code).exclude(id=course.id).exists():
            messages.error(request, 'A course with this code already exists.')
            return render(request, 'students/edit_course.html', {'course': course, 'departments': departments})
        try:
            department = get_object_or_404(Department, id=department_id)
            course.name = name
            course.code = code
            course.department = department
            course.save()
            messages.success(request, 'Course updated successfully!')
            return redirect('students:courses_list')
        except Exception as e:
            messages.error(request, f'Error updating course: {e}')
            return render(request, 'students/edit_course.html', {'course': course, 'departments': departments})

    context = {'course': course, 'departments': departments}
    return render(request, 'students/edit_course.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    course.delete()
    messages.success(request, 'Course deleted successfully!')
    return redirect('students:courses_list')

@login_required
@user_passes_test(superuser_required, login_url='login/')
def results_list(request):
    search_query = request.GET.get('search', '')
    selected_semester = request.GET.get('semester', '')
    selected_student = request.GET.get('student', '')

    results = StudentResult.objects.all()
    students = Student.objects.all()  # Add this line to provide students context
    student_dept_courses = StudentDepartmentCourse.objects.all()

    if search_query:
        results = results.filter(
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student__roll_number__icontains=search_query)
        )
    if selected_semester:
        results = results.filter(semester=selected_semester)
    if selected_student:
        results = results.filter(student_id=selected_student)

    paginator = Paginator(results, 10)
    page_number = request.GET.get('page')
    results = paginator.get_page(page_number)

    semesters = StudentResult.objects.values_list('semester', flat=True).distinct()

    context = {
        'results': results,
        'students': students,  # Ensure this is passed
        'student_dept_courses': student_dept_courses,
        'search_query': search_query,
        'selected_semester': selected_semester,
        'selected_student': selected_student,
        'semesters': semesters,
    }
    return render(request, 'students/results_list.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def subjects_list(request):
    subjects = Subject.objects.all()
    search_query = request.GET.get('search', '')

    # Apply search filter
    if search_query:
        subjects = subjects.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query)
        )

    paginator = Paginator(subjects, 5)  # 5 subjects per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'subjects': page_obj,
        'search_query': search_query,
    }
    return render(request, 'students/subjects_list.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def add_student(request):
    if not request.user.is_superuser:
        messages.error(request, 'Only superusers can add students.')
        return redirect('students:student_list')

    departments = Department.objects.all()
    courses = Course.objects.all()
    
    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        roll_number = request.POST.get('roll_number')
        email = request.POST.get('email')
        password = request.POST.get('password')
        is_active = request.POST.get('is_active') == 'on'
        department_id = request.POST.get('department')
        course_id = request.POST.get('course')

        # Basic validation
        if not all([username, first_name, last_name, roll_number, email, password]):
            messages.error(request, 'All required fields must be filled.')
            return render(request, 'students/add_student.html', {
                'departments': departments,
                'courses': courses,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'roll_number': roll_number,
                'email': email,
            })

        # Check if username or email already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'students/add_student.html', {
                'departments': departments,
                'courses': courses,
                'first_name': first_name,
                'last_name': last_name,
                'roll_number': roll_number,
                'email': email,
            })

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'students/add_student.html', {
                'departments': departments,
                'courses': courses,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'roll_number': roll_number,
            })

        # Validate roll number uniqueness
        if Student.objects.filter(roll_number=roll_number).exists():
            messages.error(request, 'Roll number already exists.')
            return render(request, 'students/add_student.html', {
                'departments': departments,
                'courses': courses,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
            })

        # Validate department/course relationship if both are provided
        department = None
        course = None
        if department_id:
            department = get_object_or_404(Department, id=department_id)
        if course_id:
            course = get_object_or_404(Course, id=course_id)
            if department and course.department != department:
                messages.error(request, 'Selected course does not belong to selected department.')
                return render(request, 'students/add_student.html', {
                    'departments': departments,
                    'courses': courses,
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name,
                    'roll_number': roll_number,
                    'email': email,
                })

        try:
            # Create User
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active
            )
            
            # Create Student
            student = Student.objects.create(
                user=user,
                roll_number=roll_number,
                first_name=first_name,
                last_name=last_name,
                email=email,
                is_active=is_active
            )
            
            # Create StudentProfile
            StudentProfile.objects.create(user=user, student=student)
            
            # Create StudentDepartmentCourse if department or course is provided
            if department or course:
                StudentDepartmentCourse.objects.create(
                    student=student,
                    department=department,
                    course=course
                )
            
            messages.success(request, f'Student {first_name} {last_name} added successfully!')
            return redirect('students:student_list')
            
        except Exception as e:
            messages.error(request, f'Error adding student: {str(e)}')
            # Delete any partially created objects
            if 'user' in locals():
                user.delete()
            return render(request, 'students/add_student.html', {
                'departments': departments,
                'courses': courses,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'roll_number': roll_number,
                'email': email,
            })

    return render(request, 'students/add_student.html', {
        'departments': departments,
        'courses': courses
    })

@login_required
@user_passes_test(superuser_required, login_url='login/')
def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    departments = Department.objects.all()
    courses = Course.objects.all()
    
    # Get the student's department and course (if assigned)
    try:
        student_dept_course = student.department_course
    except StudentDepartmentCourse.DoesNotExist:
        student_dept_course = None

    if request.method == 'POST':
        first_name = request.POST['first_name'].strip()
        last_name = request.POST['last_name'].strip()
        roll_number = request.POST['roll_number'].strip()
        email = request.POST['email'].strip()
        is_active = 'is_active' in request.POST
        department_id = request.POST.get('department')
        course_id = request.POST.get('course')

        # Validate first and last name
        if not first_name or not last_name:
            messages.error(request, 'First name and last name are required.')
            return render(request, 'students/edit_student.html', {
                'student': student,
                'student_dept_course': student_dept_course,
                'departments': departments,
                'courses': courses
            })

        # Validate roll number uniqueness (excluding the current student)
        if Student.objects.filter(roll_number=roll_number).exclude(id=student.id).exists():
            messages.error(request, 'A student with this roll number already exists.')
            return render(request, 'students/edit_student.html', {
                'student': student,
                'student_dept_course': student_dept_course,
                'departments': departments,
                'courses': courses
            })

        # Validate email uniqueness (excluding the current user)
        if User.objects.filter(email=email).exclude(id=student.user.id).exists():
            messages.error(request, 'A user with this email already exists.')
            return render(request, 'students/edit_student.html', {
                'student': student,
                'student_dept_course': student_dept_course,
                'departments': departments,
                'courses': courses
            })

        # Validate department and course
        department = None
        course = None
        if department_id:
            department = get_object_or_404(Department, id=department_id)
        if course_id:
            course = get_object_or_404(Course, id=course_id)
            if course and department and course.department != department:
                messages.error(request, 'The selected course does not belong to the selected department.')
                return render(request, 'students/edit_student.html', {
                    'student': student,
                    'student_dept_course': student_dept_course,
                    'departments': departments,
                    'courses': courses
                })

        # Update student details
        student.first_name = first_name
        student.last_name = last_name
        student.roll_number = roll_number
        student.email = email
        student.is_active = is_active
        student.user.first_name = first_name
        student.user.last_name = last_name
        student.user.email = email
        student.user.is_active = is_active
        student.save()
        student.user.save()

        # Update or create StudentDepartmentCourse entry
        if student_dept_course:
            student_dept_course.department = department
            student_dept_course.course = course
            student_dept_course.save()
        else:
            if department or course:
                StudentDepartmentCourse.objects.create(
                    student=student,
                    department=department,
                    course=course
                )

        messages.success(request, 'Student updated successfully!')
        return redirect('students:student_list')

    context = {
        'student': student,
        'student_dept_course': student_dept_course,
        'departments': departments,
        'courses': courses
    }
    return render(request, 'students/edit_student.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    student.user.delete()  # This will cascade and delete StudentDepartmentCourse as well
    messages.success(request, 'Student deleted successfully!')
    return redirect('students:student_list')


@login_required
@user_passes_test(superuser_required, login_url='login/')
def add_subject(request):
    semester_choices = [(i, f"Semester {i}") for i in range(1, 9)]  # Semesters 1-8
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        semester = request.POST.get('semester')

        form_data = {'name': name, 'code': code, 'semester': semester}

        # Validate inputs
        if not all([name, code, semester]):
            messages.error(request, 'All fields are required.')
            return render(request, 'students/add_subject.html', {
                'semester_choices': semester_choices,
                'form_data': form_data,
            })

        try:
            semester = int(semester)
            if semester not in range(1, 9):
                messages.error(request, 'Invalid semester selected.')
                return render(request, 'students/add_subject.html', {
                    'semester_choices': semester_choices,
                    'form_data': form_data,
                })

            # Check for duplicate subject code
            if Subject.objects.filter(code=code).exists():
                messages.error(request, 'Subject code already exists.')
                return render(request, 'students/add_subject.html', {
                    'semester_choices': semester_choices,
                    'form_data': form_data,
                })

            # Create subject
            Subject.objects.create(
                name=name.strip(),
                code=code.strip(),
                semester=semester
            )
            messages.success(request, 'Subject added successfully!')
            logger.info(f"Subject {name} (Code: {code}) added by {request.user.username}")
            return redirect('students:subjects_list')

        except ValueError as e:
            logger.error(f"Error adding subject: {e}")
            messages.error(request, 'Invalid semester value.')
            return render(request, 'students/add_subject.html', {
                'semester_choices': semester_choices,
                'form_data': form_data
            })

        except Exception as e:
            logger.error(f"Error adding subject: {e}")
            messages.error(request, f'Error adding subject: {str(e)}')
            return render(request, 'students/add_subject.html', {
                'semester_choices': semester_choices,
                'form_data': form_data,
            })

    context = {
        'semester_choices': semester_choices,
        'form_data': {},
    }
    return render(request, 'students/add_subject.html', context)
@login_required
@user_passes_test(superuser_required, login_url='login/')

def edit_subject(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    semester_choices = [(i, f"Semester {i}") for i in range(1, 9)]  # Semesters 1-8

    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        semester = request.POST.get('semester')

        form_data = {'name': name, 'code': code, 'semester': semester}

        # Validate inputs
        if not all([name, code, semester]):
            messages.error(request, 'All fields are required.')
            return render(request, 'students/edit_subject.html', {
                'subject': subject,
                'semester_choices': semester_choices,
                'form_data': form_data,
            })

        try:
            semester = int(semester)
            if semester not in range(1, 9):
                messages.error(request, 'Invalid semester selected.')
                return render(request, 'students/edit_subject.html', {
                    'subject': subject,
                    'semester_choices': semester_choices,
                    'form_data': form_data,
                })

            # Check for duplicate subject code (excluding current subject)
            if Subject.objects.filter(code=code).exclude(id=subject.id).exists():
                messages.error(request, 'Subject code already exists.')
                return render(request, 'students/edit_subject.html', {
                    'subject': subject,
                    'semester_choices': semester_choices,
                    'form_data': form_data,
                })

            # Update subject
            subject.name = name.strip()
            subject.code = code.strip()
            subject.semester = semester
            subject.save()
            messages.success(request, 'Subject updated successfully!')
            logger.info(f"Subject {subject.name} (Code: {subject.code}) updated by {request.user.username}")
            return redirect('students:subjects_list')

        except ValueError as e:
            logger.error(f"Error updating subject {subject.id}: {e}")
            messages.error(request, 'Invalid semester value.')
            return render(request, 'students/edit_subject.html', {
                'subject': subject,
                'semester_choices': semester_choices,
                'form_data': form_data,
            })

        except Exception as e:
            logger.error(f"Error updating subject {subject.id}: {e}")
            messages.error(request, f'Error updating subject: {str(e)}')
            return render(request, 'students/edit_subject.html', {
                'subject': subject,
                'semester_choices': semester_choices,
                'form_data': form_data,
            })

    context = {
        'subject': subject,
        'semester_choices': semester_choices,
        'form_data': {
            'name': subject.name,
            'code': subject.code,
            'semester': subject.semester,
        },
    }
    return render(request, 'students/edit_subject.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def delete_subject(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    subject.delete()
    messages.success(request, 'Subject deleted successfully!')
    return redirect('students:subjects_list')

@login_required
@user_passes_test(superuser_required, login_url='login/')
def add_result(request, student_id=None):
    students = Student.objects.all()
    if student_id:
        student = get_object_or_404(Student, id=student_id)
    else:
        student = None

    subjects = Subject.objects.all()
    if request.method == 'POST':
        if not student_id:  # Handle case where student is selected via form
            student_id = request.POST.get('student')
        if not student_id:
            messages.error(request, 'Please select a student to add a result.')
            return render(request, 'students/add_result.html', {
                'students': students,
                'subjects': subjects,
            })
        student = get_object_or_404(Student, id=student_id)
        subject_id = request.POST.get('subject')
        score = request.POST.get('score')
        semester = request.POST.get('semester')
        year = request.POST.get('year')
        remarks = request.POST.get('remarks', '')

        try:
            subject = get_object_or_404(Subject, id=subject_id)
            score = float(score)
            if not 0 <= score <= 100:
                messages.error(request, 'Score must be between 0 and 100.')
                return render(request, 'students/add_result.html', {
                    'student': student,
                    'students': students,
                    'subjects': subjects,
                })
            if score >= 90:
                grade = 'A+'
            elif score >= 80:
                grade = 'A'
            elif score >= 70:
                grade = 'B'
            elif score >= 60:
                grade = 'C'
            elif score >= 50:
                grade = 'D'
            else:
                grade = 'F'
            StudentResult.objects.create(
                student=student,
                subject=subject,
                score=score,
                grade=grade,
                semester=semester,
                year=year,
                remarks=remarks
            )
            messages.success(request, f'Result added successfully for {student.first_name} {student.last_name}.')
            return redirect('students:results_list')
        except ValueError:
            messages.error(request, 'Invalid score format.')
        except Exception as e:
            messages.error(request, f'Error adding result: {str(e)}')

    context = {
        'student': student,
        'students': students,
        'subjects': subjects,
    }
    return render(request, 'students/add_result.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def edit_result(request, result_id):
    result = get_object_or_404(StudentResult, id=result_id)
    subjects = Subject.objects.all()
    if request.method == 'POST':
        subject_id = request.POST['subject']
        try:
            score = float(request.POST['score'])
            if not (0 <= score <= 100):
                messages.error(request, 'Score must be between 0 and 100.')
                return render(request, 'students/edit_result.html', {'result': result, 'subjects': subjects})
        except ValueError:
            messages.error(request, 'Invalid score. Please enter a number.')
            return render(request, 'students/edit_result.html', {'result': result, 'subjects': subjects})

        semester = request.POST.get('semester')
        if not semester:
            messages.error(request, 'Semester is required.')
            return render(request, 'students/edit_result.html', {'result': result, 'subjects': subjects})

        try:
            year = int(request.POST.get('year'))
            if year < 1000 or year > 2099:
                messages.error(request, 'Year must be between 1000 and 2099.')
                return render(request, 'students/edit_result.html', {'result': result, 'subjects': subjects})
        except ValueError:
            messages.error(request, 'Invalid year. Please enter a valid number.')
            return render(request, 'students/edit_result.html', {'result': result, 'subjects': subjects})

        remarks = request.POST.get('remarks', '')
        subject = get_object_or_404(Subject, id=subject_id)

        if score >= 90:
            grade = 'A+'
        elif score >= 80:
            grade = 'A'
        elif score >= 70:
            grade = 'B'
        elif score >= 60:
            grade = 'C'
        elif score >= 50:
            grade = 'D'
        else:
            grade = 'F'

        result.subject = subject
        result.score = score
        result.grade = grade
        result.semester = semester
        result.year = year
        result.remarks = remarks
        result.save()
        messages.success(request, 'Result updated successfully!')
        return redirect('students:results_list')
    context = {'result': result, 'subjects': subjects}
    return render(request, 'students/edit_result.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def delete_result(request, result_id):
    result = get_object_or_404(StudentResult, id=result_id)
    result.delete()
    messages.success(request, 'Result deleted successfully!')
    return redirect('students:results_list')



from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Student, StudentProfile, StudentDepartmentCourse

@login_required
def profile(request):
    try:
        profile = StudentProfile.objects.get(user=request.user)
        student = profile.student
        try:
            student_dept_course = student.department_course
        except StudentDepartmentCourse.DoesNotExist:
            student_dept_course = None
        context = {
            'student': student,
            'student_dept_course': student_dept_course,
        }
        return render(request, 'students/profile.html', context)
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile found for your account.")
        

@login_required
def attendance(request):
    try:
        profile = StudentProfile.objects.get(user=request.user)
        student = profile.student
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile found for your account.")
        return redirect('students:student_list')

    selected_attendance_course_ids = request.GET.getlist('attendance_courses')
    attendance_start_date = request.GET.get('attendance_start_date')
    attendance_end_date = request.GET.get('attendance_end_date')
    all_attendance_courses = Course.objects.filter(lecture__attendance__student=student).distinct()
    logger.info("Fetching all_attendance_courses in attendance view: %s", all_attendance_courses.query)

    attendance_query = Attendance.objects.filter(student=student).order_by('-lecture__date')
    if selected_attendance_course_ids:
        attendance_query = attendance_query.filter(lecture__course__in=selected_attendance_course_ids)
    if attendance_start_date:
        attendance_query = attendance_query.filter(lecture__date__gte=attendance_start_date)
    if attendance_end_date:
        attendance_query = attendance_query.filter(lecture__date__lte=attendance_end_date)
    attendances = attendance_query.select_related('lecture__course', 'lecture__subject')

    context = {
        'student': student,
        'all_attendance_courses': all_attendance_courses,
        'selected_attendance_course_ids': selected_attendance_course_ids,
        'selected_attendance_start_date': attendance_start_date,
        'selected_attendance_end_date': attendance_end_date,
        'attendances': attendances,
    }
    return render(request, 'students/attendance.html', context)

@login_required
def fees(request):
    try:
        profile = StudentProfile.objects.get(user=request.user)
        student = profile.student
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile found for your account.")
        return redirect('students:student_list')

    fees = Fee.objects.filter(student=student).order_by('due_date')

    context = {
        'student': student,
        'fees': fees,
    }
    return render(request, 'students/fees.html', context)

@login_required
def results(request):
    try:
        profile = StudentProfile.objects.get(user=request.user)
        student = profile.student
    except StudentProfile.DoesNotExist:
        messages.error(request, "No student profile found for your account.")
        return redirect('students:student_list')

    selected_semester_ids = request.GET.getlist('semesters')
    selected_subject_ids = request.GET.getlist('subjects')
    all_semesters = StudentResult.objects.filter(student=student).values_list('semester', flat=True).distinct().order_by('semester')
    all_subjects = Subject.objects.filter(studentresult__student=student).distinct()

    results = StudentResult.objects.filter(student=student)
    if selected_semester_ids or selected_subject_ids:
        query = Q()
        if selected_semester_ids:
            query &= Q(semester__in=selected_semester_ids)
        if selected_subject_ids:
            query &= Q(subject__in=selected_subject_ids)
        results = results.filter(query).order_by('semester', 'subject__name')
        semesters_to_display = selected_semester_ids if selected_semester_ids else all_semesters
    else:
        semesters_to_display = all_semesters

    semester_data = []
    for semester in semesters_to_display:
        semester_results = results.filter(semester=semester)
        if semester_results.exists():
            grades = [result.grade for result in semester_results if result.grade]
            grade_counts = {grade: grades.count(grade) for grade in set(grades) if grade}
            grade_pairs = sorted([(grade, count) for grade, count in grade_counts.items()], key=lambda x: x[0])
            semester_data.append({
                'semester': semester,
                'results': semester_results,
                'grade_data': {
                    'labels': list(grade_counts.keys()),
                    'data': list(grade_counts.values()),
                },
                'grade_pairs': grade_pairs,
            })

    paginator = Paginator(results, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'student': student,
        'results': page_obj,
        'all_semesters': all_semesters,
        'selected_semester_ids': selected_semester_ids,
        'all_subjects': all_subjects,
        'selected_subject_ids': selected_subject_ids,
        'semester_data': semester_data,
    }
    return render(request, 'students/results.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def help_view(request):
    return render(request, 'help.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def assign_department_course(request):
    students = Student.objects.all()
    departments = Department.objects.all()
    courses = Course.objects.all()
    student_dept_courses = StudentDepartmentCourse.objects.all()

    if request.method == "POST":
        if "assign" in request.POST:
            student_id = request.POST.get("student")
            department_id = request.POST.get("department")
            course_id = request.POST.get("course")

            try:
                student = Student.objects.get(id=student_id)
                department = Department.objects.get(id=department_id) if department_id else None
                course = Course.objects.get(id=course_id) if course_id else None

                # Check if the student already has an assignment
                existing_assignment = StudentDepartmentCourse.objects.filter(student=student).first()
                if existing_assignment:
                    # Update existing assignment
                    existing_assignment.department = department
                    existing_assignment.course = course
                    existing_assignment.save()
                    messages.success(request, f"Updated department and course for {student.first_name} {student.last_name}.")
                else:
                    # Create new assignment
                    StudentDepartmentCourse.objects.create(
                        student=student,
                        department=department,
                        course=course
                    )
                    messages.success(request, f"Assigned department and course to {student.first_name} {student.last_name}.")

            except (Student.DoesNotExist, Department.DoesNotExist, Course.DoesNotExist):
                messages.error(request, "Invalid student, department, or course selected.")

        elif "remove" in request.POST:
            sdc_id = request.POST.get("sdc_id")
            try:
                sdc = StudentDepartmentCourse.objects.get(id=sdc_id)
                student_name = f"{sdc.student.first_name} {sdc.student.last_name}"
                sdc.delete()
                messages.success(request, f"Removed department and course assignment for {student_name}.")
            except StudentDepartmentCourse.DoesNotExist:
                messages.error(request, "Assignment not found.")

        return redirect("students:assign_department_course")

    context = {
        "students": students,
        "departments": departments,
        "courses": courses,
        "student_dept_courses": student_dept_courses,
    }
    return render(request, "assign_department_course.html", context)

class CustomPasswordResetView(PasswordResetView):
    def get_email(self, user):
        try:
            student = Student.objects.get(user=user)
            if student.email:
                logger.info(f"Retrieved email for user {user.username}: {student.email}")
                return student.email
            else:
                logger.warning(f"Student for user {user.username} has no email, using User.email: {user.email}")
                return user.email if user.email else None
        except Student.DoesNotExist:
            logger.warning(f"No Student found for user {user.username}, using User.email: {user.email}")
            return user.email if user.email else None

    def form_valid(self, form):
        email = form.cleaned_data['email']
        logger.info(f"Password reset requested for email: {email}")
        users = User.objects.filter(email=email) | User.objects.filter(student__email=email)
        logger.info(f"Found users: {[u.username for u in users]}")
        if not users.exists():
            logger.error(f"No users found for email: {email}")
            form.add_error('email', 'No account found with this email address.')
            return self.form_invalid(form)
        valid_users = []
        for user in users:
            user_email = self.get_email(user)
            if user_email:
                user.email = user_email
                valid_users.append(user)
                logger.info(f"Sending reset email to: {user_email} for user {user.username}")
            else:
                logger.warning(f"No valid email for user {user.username}, skipping")
        if not valid_users:
            logger.error(f"No users with valid emails found for email: {email}")
            form.add_error('email', 'No account with a valid email address found.')
            return self.form_invalid(form)
        self.users_cache = valid_users  # Store valid users for parent class
        return super().form_valid(form)