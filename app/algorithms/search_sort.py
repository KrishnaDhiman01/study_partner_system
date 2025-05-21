from ..models import User
from sqlalchemy import or_, func

def search_users_by_query(query):
    if not query:
        return []
    search_term = f"%{query.strip().lower()}%"
    try:
        results = User.query.filter(
            or_(
                func.lower(User.name).like(search_term),
                func.lower(User.subject).like(search_term),
                func.lower(User.email).like(search_term),
                func.lower(User.availability).like(search_term)
            )
        ).order_by(User.name.asc()).all()
        return results
    except Exception as e:
        print(f"Error during user search: {e}") 
        return []

def quick_sort(arr, key=lambda x: x):
    if len(arr) <= 1:
        return arr
    else:
        pivot_val = key(arr[len(arr) // 2])
        left = [x for x in arr if key(x) < pivot_val]
        middle = [x for x in arr if key(x) == pivot_val]
        right = [x for x in arr if key(x) > pivot_val]
        return quick_sort(left, key=key) + middle + quick_sort(right, key=key)

def sort_users_by_name(users_list):
    if not users_list:
        return []
    return quick_sort(users_list, key=lambda user: user.name.lower() if hasattr(user, 'name') and user.name else "")