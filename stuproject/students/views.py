from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Student, Subject, StudentResult, StudentProfile, Fee, Department, Course, StudentDepartmentCourse
from django.contrib.auth import authenticate, logout
from django.core.paginator import Paginator
from django.db.models import Q
import random
from datetime import datetime
from decimal import Decimal

def superuser_required(user):
    return user.is_superuser

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

        # Prepare grade distribution data for all students
        student_grade_data = []
        for student in students:
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

        # Pagination
        paginator = Paginator(students, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Fetch student department/course assignments for the current page
        student_ids = [student.id for student in page_obj]
        student_dept_courses = StudentDepartmentCourse.objects.filter(student__id__in=student_ids).select_related('student', 'department', 'course')

        # Debug: Print the student_dept_courses to verify data
        print("Student Dept Courses Queryset:", list(student_dept_courses.values('student_id', 'department__name', 'course__name')))

        context = {
            'students': page_obj,
            'search_query': search_query,
            'student_grade_data': student_grade_data,  # Keep the computed grade data
            'student_dept_courses': student_dept_courses,  # Add to context
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
    results = StudentResult.objects.all()
    students = Student.objects.all()
    semester_filter = request.GET.get('semester', '')
    student_filter = request.GET.get('student', '')

    # Apply filters
    if semester_filter:
        results = results.filter(semester=semester_filter)
    if student_filter:
        results = results.filter(student__id=student_filter)

    semesters = StudentResult.objects.values_list('semester', flat=True).distinct()

    paginator = Paginator(results, 5)  # 5 results per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'results': page_obj,
        'semesters': semesters,
        'students': students,
        'selected_semester': semester_filter,
        'selected_student': student_filter,
    }
    return render(request, 'students/results_list.html', context)

@login_required
@user_passes_test(superuser_required, login_url='login/')
def subjects_list(request):
    subjects = Subject.objects.all()
    search_query = request.GET.get('search', '')

    # Apply search filter
    if search_query:
        subjects = subjects.filter(name__icontains=search_query) | subjects.filter(code__icontains=search_query)

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
        username = request.POST['username']
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        roll_number = request.POST['roll_number']
        email = request.POST['email']
        password = request.POST['password']
        is_active = 'is_active' in request.POST
        department_id = request.POST.get('department')
        course_id = request.POST.get('course')

        # Validate department and course
        department = None
        course = None
        if department_id:
            department = get_object_or_404(Department, id=department_id)
        if course_id:
            course = get_object_or_404(Course, id=course_id)
            if course and department and course.department != department:
                messages.error(request, 'The selected course does not belong to the selected department.')
                return render(request, 'students/add_student.html', {
                    'departments': departments,
                    'courses': courses,
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name,
                    'roll_number': roll_number,
                    'email': email,
                    'is_active': is_active,
                })

        try:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                is_active=is_active
            )
            student = Student.objects.create(
                user=user,
                roll_number=roll_number,
                first_name=first_name,
                last_name=last_name,
                email=email,
                is_active=is_active
            )
            StudentProfile.objects.create(user=user, student=student)
            
            # Create the StudentDepartmentCourse entry
            StudentDepartmentCourse.objects.create(
                student=student,
                department=department,
                course=course
            )
            
            messages.success(request, 'Student added successfully!')
            return redirect('students:student_list')
        except Exception as e:
            messages.error(request, f'Error adding student: {e}')
            return render(request, 'students/add_student.html', {
                'departments': departments,
                'courses': courses,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'roll_number': roll_number,
                'email': email,
                'is_active': is_active,
            })
    return render(request, 'students/add_student.html', {'departments': departments, 'courses': courses})

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
    if request.method == 'POST':
        name = request.POST['name']
        code = request.POST['code']
        try:
            Subject.objects.create(name=name, code=code)
            messages.success(request, 'Subject added successfully!')
            return redirect('students:subjects_list')
        except Exception as e:
            messages.error(request, f'Error adding subject: {e}')
    return render(request, 'students/add_subject.html')

@login_required
@user_passes_test(superuser_required, login_url='login/')
def edit_subject(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    if request.method == 'POST':
        name = request.POST['name'].strip()
        code = request.POST['code'].strip()

        # Validate name
        if not name:
            messages.error(request, 'Subject name is required.')
            return render(request, 'students/edit_subject.html', {'subject': subject})

        # Validate code uniqueness (excluding the current subject)
        if Subject.objects.filter(code=code).exclude(id=subject.id).exists():
            messages.error(request, 'A subject with this code already exists.')
            return render(request, 'students/edit_subject.html', {'subject': subject})

        subject.name = name
        subject.code = code
        subject.save()
        messages.success(request, 'Subject updated successfully!')
        return redirect('students:subjects_list')
    context = {'subject': subject}
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
def add_result(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    subjects = Subject.objects.all()
    if request.method == 'POST':
        subject_id = request.POST['subject']
        score = float(request.POST['score'])
        semester = request.POST['semester']
        year = int(request.POST['year'])
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

        StudentResult.objects.create(
            student=student,
            subject=subject,
            score=score,
            grade=grade,
            semester=semester,
            year=year,
            remarks=remarks
        )
        messages.success(request, 'Result added successfully!')
        return redirect('students:results_list')
    context = {'student': student, 'subjects': subjects}
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

@login_required
def student_detail(request, student_id):
    if request.user.is_superuser:
        student = get_object_or_404(Student, id=student_id)
        results = StudentResult.objects.filter(student=student)
        try:
            student_dept_course = student.department_course
        except StudentDepartmentCourse.DoesNotExist:
            student_dept_course = None
    else:
        try:
            profile = StudentProfile.objects.get(user=request.user)
            student = profile.student
            if student.id != student_id:
                messages.error(request, 'You are not authorized to view this student\'s details.')
                return redirect('students:profile')
            results = StudentResult.objects.filter(student=student)
            try:
                student_dept_course = student.department_course
            except StudentDepartmentCourse.DoesNotExist:
                student_dept_course = None
        except StudentProfile.DoesNotExist:
            messages.error(request, 'No student profile found for your account.')
            return redirect('students:student_list')

    grades = [result.grade for result in results]
    grade_counts = {grade: grades.count(grade) for grade in set(grades)} if grades else {}
    grade_data = {
        'labels': list(grade_counts.keys()),
        'data': list(grade_counts.values()),
    }

    context = {
        'student': student,
        'results': results,
        'grade_data': grade_data,
        'student_dept_course': student_dept_course,
    }
    return render(request, 'students/student_detail.html', context)

@login_required
def profile(request):
    try:
        profile = StudentProfile.objects.get(user=request.user)
        student = profile.student
        
        # Get selected semesters from GET parameters for filtering
        selected_semester_ids = request.GET.getlist('semesters')
        
        # Get all semesters for the student
        all_semesters = StudentResult.objects.filter(
            student=student
        ).values_list('semester', flat=True).distinct().order_by('semester')
        
        # Filter by semesters
        if selected_semester_ids:
            results = StudentResult.objects.filter(
                student=student, 
                semester__in=selected_semester_ids
            ).order_by('semester', 'subject__name')
            semesters_to_display = selected_semester_ids
        else:
            results = StudentResult.objects.filter(
                student=student
            ).order_by('semester', 'subject__name')
            semesters_to_display = all_semesters
        
        # Prepare data for grade distribution per semester
        semester_data = []
        for semester in semesters_to_display:
            semester_results = results.filter(semester=semester)
            
            if semester_results.exists():
                grades = [result.grade for result in semester_results if result.grade]
                grade_counts = {grade: grades.count(grade) for grade in set(grades) if grade}
                
                # Create grade pairs for fallback display
                grade_pairs = sorted(
                    [(grade, count) for grade, count in grade_counts.items()],
                    key=lambda x: x[0]  # Sort by grade
                )
                
                semester_data.append({
                    'semester': semester,
                    'results': semester_results,
                    'grade_data': {
                        'labels': list(grade_counts.keys()),
                        'data': list(grade_counts.values()),
                    },
                    'grade_pairs': grade_pairs,
                })

        # Get the student's department and course
        try:
            student_dept_course = student.department_course
        except StudentDepartmentCourse.DoesNotExist:
            student_dept_course = None
        
        context = {
            'student': student,
            'semester_data': semester_data,
            'all_semesters': all_semesters,
            'selected_semester_ids': selected_semester_ids,
            'student_dept_course': student_dept_course,
        }
        return render(request, 'students/profile.html', context)
    except StudentProfile.DoesNotExist:
        messages.error(request, 'No student profile found for your account.')
        return redirect('students:student_list')

@login_required
@user_passes_test(superuser_required, login_url='login/')
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
                department = Department.objects.get(id=department_id)
                course = Course.objects.get(id=course_id)

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