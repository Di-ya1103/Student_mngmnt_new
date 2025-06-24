from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'students'

urlpatterns = [
    # Student Management URLs
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
    path('profile/attendance/', views.attendance, name='attendance'),
    path('profile/fees/', views.fees, name='fees'),
    path('profile/results/', views.results, name='results'),
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
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/add/', views.attendance_add, name='attendance_add'),
    path('attendance/edit/<int:attendance_id>/', views.attendance_edit, name='attendance_edit'),
    path('attendance/delete/<int:attendance_id>/', views.attendance_delete, name='attendance_delete'),

    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),  # Using custom logout view
   path('accounts/password_reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
        success_url='/students/accounts/password_reset/done/'  # Match this with the next path
    ), name='password_reset'),
    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/students/accounts/reset/done/'
    ), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
]