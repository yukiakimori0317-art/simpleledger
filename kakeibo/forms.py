#ログイン中の人に、他人のカテゴリを見せないための場所

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import AppSetting, Category, Expense


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["category", "amount"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(
                owner=user
            ).order_by("name")
        else:
            self.fields["category"].queryset = Category.objects.none()


class ExpenseEditForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["category", "amount", "date"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(
                owner=user
            ).order_by("name")
        else:
            self.fields["category"].queryset = Category.objects.none()


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "budget", "icon"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "項目名を入力",
            }),
            "budget": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "月予算を入力",
                "min": "0",
                "step": "1",
            }),
            "icon": forms.ClearableFileInput(attrs={
                "class": "form-control",
                "id": "id_icon",
                "accept": "image/*",
            }),
        }


class AppSettingForm(forms.ModelForm):
    class Meta:
        model = AppSetting
        fields = ["cycle_start_day"]
        widgets = {
            "cycle_start_day": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
                "max": "31",
                "placeholder": "例: 25",
            }),
        }

class SignUpForm(UserCreationForm):
    username = forms.CharField(
        label="ユーザー名",
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "ユーザー名",
            "autocomplete": "username",
        }),
    )
    password1 = forms.CharField(
        label="パスワード",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "パスワード",
            "autocomplete": "new-password",
        }),
    )
    password2 = forms.CharField(
        label="パスワード（確認）",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "パスワード（確認）",
            "autocomplete": "new-password",
        }),
    )

    class Meta:
        model = User
        fields = ["username", "password1", "password2"]

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()

        if not username:
            raise forms.ValidationError("ユーザー名を入力してください。")

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("このユーザー名は既に使われています。")

        return username