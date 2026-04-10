from django.contrib import admin
from .models import AppSetting, Category, Expense


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "budget")
    search_fields = ("name",)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "category", "amount", "created_at")
    list_filter = ("date", "category")
    search_fields = ("category__name",)
    ordering = ("-date", "-created_at")


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "cycle_start_day")