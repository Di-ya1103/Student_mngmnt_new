from django.db import models
from django.contrib.auth.models import User

class Student(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    roll_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name

class StudentResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='results')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    score = models.FloatField()
    grade = models.CharField(max_length=2)
    semester = models.CharField(max_length=20)
    year = models.IntegerField()
    remarks = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.semester}"

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student = models.OneToOneField(Student, on_delete=models.CASCADE)

    def __str__(self):
        return f"Profile for {self.user.username}"

class Fee(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()  # Added due_date field
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"Fee for {self.student} - {self.amount}"
    
    
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name
    
class Course(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')

    def __str__(self):
        return f"{self.name} ({self.department.name})"
    
class StudentDepartmentCourse(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='department_course')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.student} - Dept: {self.department} - Course: {self.course}"
    
# students/models.py
# students/models.py
class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)  # Added
    date = models.DateField()
    status = models.CharField(max_length=10, choices=[
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late')
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.date} - {self.status}"

    class Meta:
        unique_together = ('student', 'date', 'subject')  # Updated to include subject