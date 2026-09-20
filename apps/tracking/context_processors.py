from apps.tracking.services.timer import TimerService

def active_timer_context(request):
    if request.user.is_authenticated:
        active_timer = TimerService.get_active_timer(request.user)
        return {'active_timer': active_timer}
    return {'active_timer': None}
