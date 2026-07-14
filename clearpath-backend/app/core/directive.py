import asyncio
import uuid
from pathlib import Path

from app.core.state import PlanState

#helper function
def _humanize(snake_str: str) -> str:
    return " ".join(word.title() for word in snake_str.split("_"))

#human readable (90 mins to 1h 30mins)
def _format_duration(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes}min"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}min"

#main function
#checks if prev agent fails , dont generate msg -> raise error
#the module validates that all required outputs from previous agents are available
def generate_directive(state: PlanState) -> dict:
    if not state.triage or not state.spatial or not state.logistics:
        raise ValueError("Cannot generate directive: incomplete plan state")
    
    if not state.incident or not state.logistics.assignments:
        raise ValueError("Cannot generate directive: missing incident or assignments")
    
    # Extract data frm PlanState
    severity = state.triage.severity_tier  # "Low", "Medium", "High"
    duration_min = state.triage.predicted_duration_minutes
    cause = state.incident.cause or state.incident.event_cause or "Unknown Incident"
    corridor = state.incident.corridor or "main corridor"
    total_officers = state.logistics.total_officers
    buffer_m = int(state.spatial.current_buffer_radius_m)
    

    first_station = next(iter(state.logistics.assignments.keys())) if state.logistics.assignments else "nearest station"
    
    # Format duration
    duration_str = _format_duration(duration_min)
    
    # Humanize cause
    cause_humanized = _humanize(cause) if "_" in cause else cause

    delta_min = state.spatial.delta_minutes
    delta_clause = f" Diversion adds ~{delta_min:.1f} min to your route." if delta_min >= 0.5 else ""
    
    # Build tweet (~280 chars, Twitter limit)
    tweet = (
        f" {severity} priority {cause_humanized} reported on {corridor}. "
        f"Estimated clearance: {duration_str}. {total_officers} officers deployed."
        f"{delta_clause}"
    )
    # Trim if over 280
    if len(tweet) > 280:
        tweet = tweet[:277] + "..."
    #build sms
    sms = (
        f"ClearPath Alert: {cause_humanized} on {corridor}. "
        f"Buffer zone: {buffer_m}m radius. "
        f"Estimated clearance: {duration_str}.{delta_clause} Plan alternate route."
    )
    dispatch_script_spoken=(
        f"All units, {severity.lower()} priority {cause_humanized.lower()} "
        f"reported on {corridor}. "
        f"Station {first_station}, deploy {total_officers} units immediately. "
        f"Estimated clearance {duration_str}. Acknowledge."
    )
    dispatch_script_written = (
         f"All units, {severity.lower()} priority {cause_humanized.lower()} "
    f"reported at {state.incident.lat:.4f}, {state.incident.lng:.4f} ({corridor}). "
    f"Station {first_station}, deploy {total_officers} units immediately. "
    f"Estimated clearance {duration_str}. Acknowledge."
    )
    
    #returns dictionary
    return {
        "tweet": tweet,
        "sms": sms,
        "dispatch_script_spoken": dispatch_script_spoken,
        "dispatch_script_written": dispatch_script_written,
    }

#converts dispatch script -> gtts(mp3)
async def synthesize_dispatch_audio(dispatch_script: str, output_dir: str) -> str:
    try:
        from gtts import gTTS
    except ImportError:
        raise ImportError(
            "gtts library not installed. Install with: "
            "pip install gtts --break-system-packages"
        )
    
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename (avoids overwriting on old files)
    filename = f"dispatch_{uuid.uuid4().hex[:8]}.mp3"
    filepath = output_path / filename
    
    #generating audio(tts) is blocking operation,hence work on another thread s.t. backend stays responsive
    def _synthesize():
        """Blocking gTTS call wrapped for asyncio.to_thread."""
        tts = gTTS(text=dispatch_script, lang="en", tld="co.in")
        tts.save(str(filepath))
    
    await asyncio.to_thread(_synthesize)
    
    return filename
