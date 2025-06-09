from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('', views.student_list, name='student_list'),
    path('fees/', views.fees_list, name='fees_list'),
    path('fees/add/', views.add_fee, name='add_fee'),
    path('fees/edit/<int:fee_id>/', views.edit_fee, name='edit_fee'),
    path('fees/delete/<int:fee_id>/', views.delete_fee, name='delete_fee'),
    path('results/', views.results_list, name='results_list'),
    path('subjects/', views.subjects_list, name='subjects_list'),
    path('add/', views.add_student, name='add_student'),
    path('edit/<int:student_id>/', views.edit_student, name='edit_student'),
    path('delete/<int:student_id>/', views.delete_student, name='delete_student'),
    path('subject/add/', views.add_subject, name='add_subject'),
    path('subject/edit/<int:subject_id>/', views.edit_subject, name='edit_subject'),
    path('subject/delete/<int:subject_id>/', views.delete_subject, name='delete_subject'),
    path('result/add/<int:student_id>/', views.add_result, name='add_result'),
    path('result/edit/<int:result_id>/', views.edit_result, name='edit_result'),
    path('result/delete/<int:result_id>/', views.delete_result, name='delete_result'),
    path('detail/<int:student_id>/', views.student_detail, name='student_detail'),
    path('profile/', views.profile, name='profile'),
    path('help/', views.help_view, name='help'),
    path('departments/', views.departments_list, name='departments_list'),
    path('departments/add/', views.add_department, name='add_department'),
    path('departments/edit/<int:department_id>/', views.edit_department, name='edit_department'),
    path('departments/delete/<int:department_id>/', views.delete_department, name='delete_department'),
    path('courses/', views.courses_list, name='courses_list'),
    path('courses/add/', views.add_course, name='add_course'),
    path('courses/edit/<int:course_id>/', views.edit_course, name='edit_course'),
    path('courses/delete/<int:course_id>/', views.delete_course, name='delete_course'),
    path("assign-department-course/", views.assign_department_course, name="assign_department_course"),
]