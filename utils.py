# utils.py
def get_consecutive_days_below(df, col, threshold):
    below = df[col] < threshold
    count = 0
    for b in below[::-1]:
        if b:
            count += 1
        else:
            break
    return count

def get_weather_icon(event):
    if event == "Lluvia":
        return "🌧️"
    elif event == "Normal":
        return "☀️"
    elif event == "Sin API Key":
        return "❓"
    else:
        return "⚠️"
