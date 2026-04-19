from .models import Profile


def nickname_context(request):
    if not request.user.is_authenticated:
        return {"header_nickname": ""}

    profile, _ = Profile.objects.get_or_create(user=request.user)

    nickname = profile.nickname.strip() if profile.nickname else ""
    if not nickname:
        nickname = request.user.username

    return {"header_nickname": nickname}