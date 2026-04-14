from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


# カテゴリ1件ごとに、そのカテゴリの持ち主ユーザーを保存する
#カテゴリ自体に owner が入る
class Category(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
        verbose_name="所有ユーザー",
    )
    name = models.CharField("項目名", max_length=20)
    budget = models.PositiveIntegerField("月予算", default=0)



    def __str__(self):
        return self.name


# アプリ全体の設定
class AppSetting(models.Model):
    cycle_start_day = models.PositiveSmallIntegerField(
        "集計開始日",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        help_text="毎月の集計開始日（給料日など）",
    )

    def __str__(self):
        return f"集計開始日: {self.cycle_start_day}日"


# 支出1件ごとに、誰のものか、どのカテゴリか
class Expense(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expenses",
        verbose_name="所有ユーザー",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="expenses",
        verbose_name="項目",
    )
    amount = models.PositiveIntegerField("金額")
    date = models.DateField("日付", default=timezone.localdate)
    created_at = models.DateTimeField("登録日時", auto_now_add=True)

    def __str__(self):
        return f"{self.date} {self.category.name} {self.amount}円"