from .signals import set_actor


class ActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            set_actor(request.user)
        else:
            set_actor(None)
        return self.get_response(request)
