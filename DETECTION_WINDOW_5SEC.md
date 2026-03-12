# Pattern Matching 5-Second Detection Windows

## What Changed 🎯

You now have a comprehensive **5-second windowed detection system** that:
- ✅ Runs pattern matching every 5 seconds on accumulated CSI data
- ✅ Shows historical pattern matching scores in a live-updating graph
- ✅ Displays confidence, margin, and frame counts for each 5-second window
- ✅ Uses time-based labels ("5s ago", "10s ago") for clarity
- ✅ Compares raw CSI data against reference patterns every 5 seconds

## How It Works 🔄

### Backend (Python)
```python
# Detection runs every 5 seconds on accumulating CSI window
Detection Window:     [========] (7 seconds of CSI data)
Detection Interval:   <-- 5 seconds -->
Last Detection:       ·
Next Detection:       [in 5 seconds]
```

**Process:**
1. CSI frames arrive continuously from ESP32
2. Every 5 seconds, pattern detection runs on the last 7 seconds of data
3. Compares accumulated CSI signatures against empty/occupied/multi reference patterns
4. Stores: confidence, margin, individual scores (empty%, occupied%, multi%)
5. Frontend polls every ~200ms and displays results

### Frontend (JavaScript)
```
API Response → score_history array
    ↓
Graph Data (empty%, occupied%, multi% over time)
    ↓
Time Labels (convert timestamps to "5s ago", "10s ago")
    ↓
Detection Table (shows latest 15 windows)
    ↓
Visual Display
```

## Data Structure 📊

Each 5-second detection window captures:

```json
{
  "timestamp": 1773245650.123,        // Unix timestamp
  "seconds_ago": 0,                   // For display
  "window_index": 42,                 // Which 5-sec window (1st, 2nd, 3rd...)
  "empty": 42.5,                      // Match score for empty pattern (%)
  "occupied": 71.3,                   // Match score for occupied pattern (%)
  "multi": 28.1,                      // Match score for multiple people (%)
  "not_empty": 71.3,                  // Max(occupied, multi)
  "confidence": 71.3,                 // Confidence in best match
  "margin": 28.8,                     // Gap between top and 2nd best (71.3 - 42.5)
  "state": "occupied",                // Decision: empty/occupied/multi
  "frames_analyzed": 156              // CSI frames in this window
}
```

## Graph Display 📈

### What You See
- **X-Axis**: Time labels ("Now", "5s ago", "10s ago", etc.)
- **Y-Axis**: Score percentage (0-100%)
- **Green Line**: Empty room score
- **Blue Line**: Person detected score
- **Red Line**: Multiple people score
- **Points**: Visible dots at each 5-second window

### What It Means
- **High green, low blue/red** → Empty room
- **High blue, low green/red** → One person
- **High red, mixed others** → Multiple people
- **Crossover lines** → Transition periods (e.g., person entering)

## Detection History Table 📋

Shows the last 15 5-second windows with:
- **State emoji**: 🟢=empty, 🔵=person, 🔴=multi, ⚪=unknown
- **Time ago**: When this window ran (seconds)
- **Score**: Winning pattern score
- **Confidence**: How sure about this match
- **Margin**: Gap to 2nd place (✓ = margin ≥ 8, good discrimination)
- **Frames**: How many CSI samples in this window

## Configuration 🔧

**File**: `python/app.py`

```python
CONFIG = {
    'detection_window_seconds': 7.0,      # Analyze this much CSI data
    'detection_update_interval': 5.0,     # Run detection every 5 seconds
    'min_frames_for_detection': 50,       # Need this many frames to detect
}
```

### What This Means:
- Every 5 seconds, detection analyzes the last 7 seconds of CSI data
- Need at least 50 CSI frames (≈ 0.5-1 second of raw data)
- Typically 100-150 frames available for pattern matching

## How to Interpret Results 🎯

### Healthy Detection Sequence
```
Time   Empty  Person  Multi   State         Margin
-----  -----  ------  -----   -----         ------
 0s    65%    25%     10%     🟢 EMPTY      40
-5s    62%    28%     12%     🟢 EMPTY      34
-10s   45%    52%     18%     🔵 PERSON     7    ⚠️ Low margin
-15s   28%    71%     15%     🔵 PERSON     43   ✓ Good
-20s   15%    72%     20%     🔵 PERSON     52   ✓ Good
```

### Key Observations:
✅ Stable states maintain high margin (> 8)
✅ Transitions show crossover (scores getting closer)
⚠️ Low margin (< 3) = uncertain, might switch
✗ All scores < 35 = insufficient frames/data

## Testing the Feature 🧪

### Test Setup:
1. Open browser: http://localhost:8080
2. Go to "Live Data & Detection" page
3. Watch the "Pattern Match Scores — History" chart
4. Look for the detection history table below

### Test Sequence:
1. **Start empty (30 sec)**: Graph should show high green line
2. **Enter room**: Graph transitions to blue line
3. **Walk around**: Blue stays high, green stays low
4. **Leave room**: Graph transitions back to green

### Expected Pattern:
```
     Green
      ▲
  100 │ ╭───           empty room
      │ │   │ 
   70 │ │   ├────┐
      │ │   │    │     entering
   50 │ │   │    ├──∧∧∧∧──  person present
      │ │   │    │   └└└└
   30 │ ╰───┴────┴─────     leaving
      │
    0 └─────────────────────────→ Time
```

## Monitoring Quality 📊

### Good Detection:
- Margin consistently > 8
- Confidence > 55%
- Clear peaks in winning score
- Smooth transitions (no erratic jumps)

### Poor Detection:
- Frequent margin < 3
- Confidence drifts 30-50%
- Multiple lines similar height
- Rapid state changes

**Fix**: Recalibrate with more training data (collect 60+ sec per state)

## Technical Details 🔬

### Matching Process (every 5 seconds):
1. **Extract features** from 7-sec CSI window
   - 156 CSI frames typically available
   - Features: variance, entropy, spectral properties

2. **Calculate distances** to reference patterns
   - Empty pattern (from data2/myroom/empty.txt)
   - Occupied pattern (from data2/myroom/occupied.txt)  
   - Multi pattern (from data2/myroom/multiple_people.txt)

3. **Score each pattern** using weighted Mahalanobis distance
   - Variance features weighted 3-3.5x (key discriminator)
   - Result: 0-100% match score

4. **Determine best match** and margin
   - Best = highest score
   - Margin = best - 2nd best
   - If margin > 8 and confidence > 55: CONFIDENT

5. **Store in history**
   - One entry per 5-second window
   - Kept for last 60 windows (5 minutes)
   - Display updates every 200ms

### Raw CSI Matching:
- **Raw CSI**: 128 signed integer values per frame (amplitude changes)
- **Normalized**: Convert to frequency domain (FFT → 64-bin spectrum)
- **Enhanced**: Apply variance weighting to emphasize temporal dynamics
- **Matched**: Compare against reference patterns using distance metric

## Performance Notes 📈

- **CPU**: Pattern matching expensive (~10-20ms per run, but only every 5 sec)
- **Memory**: 300 CSI frames + history = ~1-2 MB
- **Latency**: 5-second delay before detection result (by design)
- **Accuracy**: Improves with more training data (100+ frames per state ideal)

## Troubleshooting 🔧

| Issue | Cause | Solution |
|-------|-------|----------|
| Graph shows very small/flat lines | All scores low (< 35) | Wait 30+ seconds for startup, ensure CSI data flowing |
| Constant oscillation between states | Margin always < 3 | Recalibrate patterns with more data |
| Always shows EMPTY even with people | Empty pattern matches too well | Adjust pattern data quality, collect new empty data |
| Confidence always 0% | Detection not running | Check if 50+ frames collected, view server logs |

## Files Modified ✏️

1. **python/app.py**
   - Added `detection_history` deque (line ~63)
   - Enhanced `_periodic_detection_update()` to track windows (line ~164)
   - Improved API response with detailed history (line ~352)

2. **python/templates/monitor.html**
   - New `updateScoreChart()` function with time labels
   - Enhanced `initScoreChart()` with larger points and better styling
   - Added Detection History Table display
   - Responsive chart sizing

## What's Next 🚀

The 5-second windowed detection is now ready. You can:
1. ✅ Watch pattern matching scores evolve over time
2. ✅ See exact confidence and margin for each 5-second window
3. ✅ Monitor transitions as people enter/leave
4. ✅ Debug detection issues by examining the history table
5. ✅ Recalibrate patterns if accuracy needs improvement

**Browser Access**: Refresh (Cmd+Shift+R) and navigate to "Live Data & Detection" page
