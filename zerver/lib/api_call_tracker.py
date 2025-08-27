from zerver.models import UserProfile
from zerver.lib.rate_limiter import RateLimitedObject, RateLimitedUser


def api_tracker() -> None:
    while True:
        diapyr_bot = UserProfile.objects.get(full_name="Potobot")
        try:
            api_tool = RateLimitedUser(diapyr_bot)
            api_call = api_tool.api_calls_left()
            print(api_call)
        except Exception as e:
            raise e
    
