import heapq
import traceback
import re 

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

DAYS_MAP = {
    "mon": "mon", "monday": "mon",
    "tue": "tue", "tuesday": "tue", "tues": "tue",
    "wed": "wed", "wednesday": "wed",
    "thu": "thu", "thursday": "thu", "thur": "thu", "thurs": "thu",
    "fri": "fri", "friday": "fri",
    "sat": "sat", "saturday": "sat",
    "sun": "sun", "sunday": "sun",
}
TIMES_OF_DAY_MAP = {
    "morning": "am", "morn": "am", "am": "am", "forenoon": "am",
    "afternoon": "pm", "aft": "pm", "noon": "pm", "pm": "pm", 
    "evening": "eve", "eve": "eve", "night": "eve", 
}
ALL_DAY_SLOTS = ["am", "pm", "eve"] 
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri"]
WEEKEND_DAYS = ["sat", "sun"]

def parse_availability(avail_str):
    slots = set()
    if not avail_str: return slots
    
    normalized_str = avail_str.lower().strip()
    normalized_str = re.sub(r'[\s-]+', ' ', normalized_str) 
    normalized_str = re.sub(r'[\/,;]', ',', normalized_str)
    normalized_str = re.sub(r'\s*to\s*|\s*-\s*', '-', normalized_str) 

    parts = [part.strip() for part in normalized_str.split(',') if part.strip()]

    for part_orig in parts:
        part = part_orig
        
        current_days = set()
        current_times_of_day = set() 
        current_specific_hours = set() 

        if "weekday" in part:
            current_days.update(WEEKDAYS)
            part = re.sub(r'weekdays?', '', part).strip()
        elif "weekend" in part:
            current_days.update(WEEKEND_DAYS)
            part = re.sub(r'weekends?', '', part).strip()
       
        temp_part = part
        matched_day_keys = []
        sorted_day_keys = sorted(DAYS_MAP.keys(), key=len, reverse=True)

        for day_key in sorted_day_keys:
            pattern = r'\b' + re.escape(day_key) + r'\b'
            if re.search(pattern, temp_part):
                current_days.add(DAYS_MAP[day_key])
                temp_part = re.sub(pattern, '', temp_part).strip()
        part = temp_part

        if any(keyword in part for keyword in ["all day", "allday", "anytime", "any time"]):
            current_times_of_day.update(ALL_DAY_SLOTS)
            part = re.sub(r'(all day|allday|anytime|any time)', '', part).strip()
        else:
            temp_part_time = part
            for time_key, time_val in TIMES_OF_DAY_MAP.items():
                pattern = r'\b' + re.escape(time_key) + r'\b'
                if re.search(pattern, temp_part_time):
                    current_times_of_day.add(time_val)
        
        hour_ranges = re.findall(r'(\d{1,2})\s*(?:(am|pm|eve))?\s*(?:-\s*(\d{1,2})\s*(?:(am|pm|eve))?)?', part)

        for start_hour_str, start_ampm, end_hour_str, end_ampm in hour_ranges:
            try:
                start_h = int(start_hour_str)
                
                start_ampm_norm = start_ampm
                if start_ampm == 'eve': start_ampm_norm = 'pm'

                h_24_start = start_h
                if start_ampm_norm == 'pm' and 1 <= start_h <= 11: h_24_start += 12
                elif start_ampm_norm == 'am' and start_h == 12: h_24_start = 0

                if end_hour_str:
                    end_h = int(end_hour_str)
                    end_ampm_norm = end_ampm
                    if end_ampm == 'eve': end_ampm_norm = 'pm'
                    
                    if not end_ampm_norm and start_ampm_norm:
                        if end_h < start_h or (end_h == 12 and start_h != 12) :
                           end_ampm_norm = 'pm' if start_ampm_norm == 'am' else 'am'
                        else:
                           end_ampm_norm = start_ampm_norm

                    h_24_end = end_h
                    if end_ampm_norm == 'pm' and 1 <= end_h <= 11: h_24_end += 12
                    elif end_ampm_norm == 'am' and end_h == 12: h_24_end = 0
                    
                    if h_24_end <= h_24_start and (start_ampm or end_ampm) :
                        h_24_end += 24

                    for h in range(h_24_start, h_24_end):
                        hour_12 = h % 12
                        if hour_12 == 0: hour_12 = 12
                        
                        current_slot_ampm = "am"
                        if 0 <= h <= 5 : current_slot_ampm = "am"
                        elif 6 <= h <= 11 : current_slot_ampm = "am"
                        elif 12 <= h <= 17: current_slot_ampm = "pm"
                        elif 18 <= h <= 23: current_slot_ampm = "eve"
                        
                        current_specific_hours.add(f"{hour_12}{current_slot_ampm}")
                else:
                    final_ampm_suffix = start_ampm if start_ampm else ("am" if 7 <= start_h <= 11 else ("pm" if 1 <= start_h <= 6 or start_h == 12 else "eve"))
                    current_specific_hours.add(f"{start_h}{final_ampm_suffix}")

            except ValueError:
                continue

        if not current_days:
            if "weekday" in part_orig or "weekend" not in part_orig:
                current_days.update(WEEKDAYS)
            else:
                  pass

        if current_days and not current_times_of_day and not current_specific_hours:
            current_times_of_day.update(ALL_DAY_SLOTS)

        if current_days and current_specific_hours:
            for day in current_days:
                for hour_slot in current_specific_hours:
                    slots.add(f"{day}_{hour_slot}")
        
        if current_days and current_times_of_day:
            for day in current_days:
                day_has_specific_hours = any(s.startswith(f"{day}_") and s[-2:].isdigit() for s in current_specific_hours)
                
                if not day_has_specific_hours or not current_specific_hours:
                    for tod_slot in current_times_of_day:
                        slots.add(f"{day}_{tod_slot}")
    return slots

def calculate_availability_overlap_score(slots1, slots2):
    if not slots1 or not slots2: return 0.0
    intersection = len(slots1.intersection(slots2))
    union = len(slots1.union(slots2))
    return float(intersection) / float(union) if union > 0 else 0.0

def calculate_subject_similarity(subj1, subj2):
    s1 = subj1.strip().lower() if subj1 else ""
    s2 = subj2.strip().lower() if subj2 else ""
    if not s1 or not s2: return 0.0
    if s1 == s2: return 1.0
    s1_words = set(s1.split())
    s2_words = set(s2.split())
    common_words = len(s1_words.intersection(s2_words))
    if common_words == 0: return 0.0
    return float(common_words) / float(len(s1_words.union(s2_words)))

def calculate_preference_similarity(pref1, pref2):
    p1 = pref1.strip().lower() if pref1 else None
    p2 = pref2.strip().lower() if pref2 else None
    if p1 is None and p2 is None: return 1.0
    if p1 is None or p2 is None: return 0.3
    if p1 == p2: return 1.0
    p1_words = set(p1.split())
    p2_words = set(p2.split())
    common_words = len(p1_words.intersection(p2_words))
    if common_words > 0:
        return 0.5 + 0.5 * (float(common_words) / float(len(p1_words.union(p2_words))))
    return 0.0

def calculate_compatibility_weight(user1, user2):
    W_SUBJECT = 100.0
    W_AVAILABILITY = 50.0
    W_PREFERENCE = 20.0

    if not user1 or not user2 or not hasattr(user1, 'id') or not hasattr(user2, 'id'):
        return float('inf')

    subject_sim = calculate_subject_similarity(
        getattr(user1, 'subject', ''), getattr(user2, 'subject', '')
    )
    pref_sim = calculate_preference_similarity(
        getattr(user1, 'preference', None), getattr(user2, 'preference', None)
    )
    
    avail_sim = 0.0
    try:
        slots1 = parse_availability(getattr(user1, 'availability', ''))
        slots2 = parse_availability(getattr(user2, 'availability', ''))
        avail_sim = calculate_availability_overlap_score(slots1, slots2)
    except Exception as e:
        print(f"Warning: Availability calculation failed for users {getattr(user1,'id','N/A')}/{getattr(user2,'id','N/A')}: {e}")
        avail_sim = 0.0

    subject_dist = 1.0 - subject_sim
    avail_dist = 1.0 - avail_sim
    pref_dist = 1.0 - pref_sim

    total_distance = (
        (subject_dist * W_SUBJECT) +
        (avail_dist * W_AVAILABILITY) +
        (pref_dist * W_PREFERENCE)
    )
    total_distance += 0.01
    return total_distance

def build_user_graph(users):
    if not users: return {}, {}
    valid_users = [u for u in users if hasattr(u, 'id')]
    graph = {user.id: {} for user in valid_users}
    user_map = {user.id: user for user in valid_users}

    if not graph: return {}, {}

    user_list = list(user_map.values())
    for i in range(len(user_list)):
        for j in range(i + 1, len(user_list)):
            user_i = user_list[i]
            user_j = user_list[j]
            
            if user_i.id not in graph or user_j.id not in graph:
                continue

            weight = calculate_compatibility_weight(user_i, user_j)
            
            graph[user_i.id][user_j.id] = weight
            graph[user_j.id][user_i.id] = weight
            
    return graph, user_map

def dijkstra_find_partners(graph, start_user_id):
    if not graph or start_user_id not in graph:
        return None 

    distances = {node_id: float('inf') for node_id in graph}
    if start_user_id not in distances:
        return None
        
    distances[start_user_id] = 0
    pq = [(0, start_user_id)]
    processed_nodes = set()

    while pq:
        current_distance, current_node_id = heapq.heappop(pq)

        if current_node_id in processed_nodes:
            continue 
        if current_distance > distances[current_node_id]:
             continue

        processed_nodes.add(current_node_id)

        for neighbor_id, weight in graph.get(current_node_id, {}).items():
            if neighbor_id not in distances:
                continue
            
            distance_through_current = current_distance + weight
            if distance_through_current < distances[neighbor_id]:
                 distances[neighbor_id] = distance_through_current
                 heapq.heappush(pq, (distance_through_current, neighbor_id))
                 
    distances.pop(start_user_id, None)
    return distances

def vectorize_user(user, all_subjects_map=None, all_preferences_map=None):
    subject_vector = [0.0] * len(all_subjects_map) if all_subjects_map else []
    user_subject = getattr(user, 'subject', '').strip().lower()
    if all_subjects_map and user_subject in all_subjects_map:
        subject_vector[all_subjects_map[user_subject]] = 1.0

    availability_score = 0.0
    try:
        availability_slots = parse_availability(getattr(user, 'availability', ''))
        max_expected_slots = 7 * (len(ALL_DAY_SLOTS) + 4)
        availability_score = min(float(len(availability_slots)) / max_expected_slots, 1.0) if max_expected_slots > 0 else 0.0
    except Exception as e:
        availability_score = 0.0

    preference_vector = [0.0] * len(all_preferences_map) if all_preferences_map else []
    user_pref_lower = getattr(user, 'preference', '').strip().lower()
    if all_preferences_map and user_pref_lower in all_preferences_map:
        preference_vector[all_preferences_map[user_pref_lower]] = 1.0
    
    combined_vector = subject_vector + [availability_score] + preference_vector
    return combined_vector

def kmeans_cluster_users(users, k=3):
    if not SKLEARN_AVAILABLE:
        print("K-Means clustering unavailable: scikit-learn library not installed.")
        return None

    if not users or len(users) < k:
        return [[user.id for user in users]] if users else []

    all_unique_subjects = sorted(list(set(u.subject.strip().lower() for u in users if hasattr(u, 'subject') and u.subject)))
    all_subjects_map = {subject: i for i, subject in enumerate(all_unique_subjects)}
    
    all_unique_preferences = sorted(list(set(u.preference.strip().lower() for u in users if hasattr(u, 'preference') and u.preference)))
    all_preferences_map = {pref: i for i, pref in enumerate(all_unique_preferences)}
    
    user_vectors = []
    user_ids_for_vectors = []
    
    expected_vector_length = 0 
    if all_subjects_map: expected_vector_length += len(all_subjects_map)
    expected_vector_length += 1 
    if all_preferences_map: expected_vector_length += len(all_preferences_map)

    for user in users:
        if not hasattr(user, 'id'): continue

        try:
            vector = vectorize_user(user, all_subjects_map, all_preferences_map)
            if vector and len(vector) == expected_vector_length and all(isinstance(v, (int, float)) for v in vector):
                user_vectors.append(vector)
                user_ids_for_vectors.append(user.id)
            else:
                pass
        except Exception as e:
            pass

    if len(user_vectors) < k:
        return [user_ids_for_vectors] if user_ids_for_vectors else []

    try:
        scaler = StandardScaler()
        vectors_scaled = scaler.fit_transform(user_vectors)
        
        kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
        kmeans.fit(vectors_scaled)
        labels = kmeans.labels_
        
        final_clusters_of_ids = [[] for _ in range(k)]
        for i, label in enumerate(labels):
            original_user_id = user_ids_for_vectors[i]
            if 0 <= label < k:
                 final_clusters_of_ids[label].append(original_user_id)
            else:
                 pass
        
        non_empty_clusters = [cluster_ids for cluster_ids in final_clusters_of_ids if cluster_ids]
        return non_empty_clusters

    except Exception as e:
        return None