from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

from . import views

app_name = 'kakeibo'

urlpatterns = [
    path('', views.index, name='index'),
    path('ajax/add/', views.ajax_add_expense, name='ajax_add_expense'),

    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    path('history/', views.history, name='history'),
    path('month-history/', views.month_history, name='month_history'),
    path('summary/', views.summary, name='summary'),
    path('expense/<int:pk>/edit/', views.expense_edit, name='expense_edit'),
    path('expense/<int:pk>/delete/', views.expense_delete, name='expense_delete'),
    path('ajax/summary/', views.get_summary, name='get_summary'),

    path(
        'accounts/login/',
        auth_views.LoginView.as_view(template_name='registration/login.html'),
        name='login'
    ),
    path('accounts/signup/', views.signup, name='signup'),
    path(
    'accounts/logout/',
    auth_views.LogoutView.as_view(next_page='kakeibo:login'),
    name='logout'
    ),
    path("manifest.webmanifest", views.pwa_manifest, name="pwa_manifest"),
    path("service-worker.js", views.service_worker, name="service_worker"),
        

]

