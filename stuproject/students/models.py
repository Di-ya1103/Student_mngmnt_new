from django.db import models
from django.contrib.auth.models import User

# Student model (unchanged)
class Student(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    roll_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

# Department model (unchanged)
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name

# Course model (unchanged, already aligns with mentor’s but includes department)
class Course(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')

    def __str__(self):
        return f"{self.name} ({self.department.name})"

# Subject model (unchanged)
class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    semester = models.CharField(max_length=20)

    def __str__(self):
        return self.name

# Enrollment model (new, inspired by mentor’s Enrollment)
class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student} enrolled in {self.course.name}"

# Lecture model (updated with time field)
class Lecture(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)  # Remove null=True, blank=True
    date = models.DateField()
    time = models.TimeField()  # New field for lecture time
    students = models.ManyToManyField(Student, related_name='lectures', blank=True)

    def __str__(self):
        return f"{self.course.name} - {self.date} {self.time}"

# Attendance model (modified to align with mentor’s structure)
class Attendance(models.Model):
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
    ]

    lecture = models.ForeignKey(Lecture, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('lecture', 'student')

    def __str__(self):
        return f"{self.student} - {self.status} for {self.lecture}"

# StudentResult model (unchanged)
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

# StudentProfile model (unchanged)
class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student = models.OneToOneField(Student, on_delete=models.CASCADE)

    def __str__(self):
        return f"Profile for {self.user.username}"

# Fee model (unchanged)
class Fee(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"Fee for {self.student} - {self.amount}"

# StudentDepartmentCourse model (optional, can be kept or removed)
class StudentDepartmentCourse(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='department_course')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.student} - Dept: {self.department} - Course: {self.course}"