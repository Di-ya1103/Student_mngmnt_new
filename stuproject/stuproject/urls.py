
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('students/', include('students.urls')),
    path('', include('students.urls')),
    path('students/accounts/', include('django.contrib.auth.urls')),
    path('', lambda request: redirect('students:student_list'), name='home'),
]
