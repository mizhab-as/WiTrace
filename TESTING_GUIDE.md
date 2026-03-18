# Testing Guide for Improved Pattern Detection

## Quick Start
1. **Start the server** (now running with improved detection)
2. **Open browser** to http://localhost:8080
3. **Go to "Live Data & Detection" page**
4. **Test scenarios below**

## Test Scenarios

### ✅ Test 1: Empty Room Detection
**What to do:**
- Leave the room completely empty and silent
- Wait 30-60 seconds of no activity
- Stand from detection area (distance matters for WiFi CSI)

**Expected result:**
- Status shows: `🟢 EMPTY ROOM`
- Confidence > 55
- Margin > 8 (significant separation from occupied pattern)

---

### ✅ Test 2: Single Person Detection
**What to do:**
- Stand or sit in room
- Move slightly (WiFi CSI detects movement well)
- Wait 10-15 seconds

**Expected result:**
- Status shows: `🔵 PERSON DETECTED`
- Confidence > 60-70
- Margin > 8 to empty room

---

### ✅ Test 3: Multiple People Detection
**What to do:**
- Have 2+ people in room
- Move around naturally (walking, gestures)
- Wait 10-15 seconds

**Expected result:**
- Status shows: `🔴 MULTIPLE PEOPLE`
- Confidence > 60-70
- Clear separation from single-person pattern

---

### ✅ Test 4: Edge Case - Very Quiet Single Person
**What to do:**
- One person sitting still and not moving
- Minimize breathing/movement sounds
- Wait 30 seconds

**Expected result:**
- May show `🟢 EMPTY ROOM` initially (no movement)
- **Then shifts to** `🔵 PERSON DETECTED` once slight movements detected
- (This is normal - WiFi detects dynamic motion primarily)

---

### ✅ Test 5: Detection Margin Reporting
**What to do:**
- Monitor the debug console/API
- Check `margin` and `scores` values during transitions

**Expected results:**
- **Clear decision:** margin > 8, top score > 55
- **Ambiguous case:** margin 3-8 (may use fallback logic)
- **Weak signal:** any score < 35 (should show INITIALIZING first)

---

## Understanding the Output

```json
{
  "detection_status": "🔵 PERSON DETECTED",
  "detection_scores": {
    "empty": 28.5,           // Low (incorrect match)
    "occupied": 65.2,        // High and winning
    "multi": 42.3            // Medium
  },
  "detection_margin": 8.4,   // Significant gap (65.2 - 56.8)
  "detection_confidence": 65.2,  // Confidence in top match
  "binary_margin": 36.7,     // Huge gap: occupied (65.2) vs empty (28.5)
  "method": "weighted_mahalanobis_matching"  // ← New method
}
```

### Score Interpretation:
- **Score > 55**: Likely correct match
- **Score 35-55**: Borderline/uncertain
- **Score < 35**: Not a good match
- **Margin > 8**: High confidence in distinction
- **Margin 3-8**: Using fallback logic (improved)
- **Margin < 3**: Very uncertain

---

## Key Improvements Explained

### Why Fewer False "Empty" Results?
1. **Variance features weighted 3.0-3.5x** instead of 1.0
   - Empty room = steady signal = low variance
   - Occupied room = moving people = high variance
   - Algorithm now heavily prioritizes variance features

2. **Stricter similarity decay** (exp(-1.2x) instead of exp(-0.75x))
   - More aggressive rejection of poor matches
   - Only excellent matches score > 55

3. **Margin requirement > 8** (was 3)
   - Must clearly beat other patterns
   - Prevents borderline "empty" classifications

### Enhanced Moving Variance
- Recent time windows weighted more heavily
- Better captures recent human movements
- More responsive to occupancy changes

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Still shows empty when occupied | Pattern file not trained well | Recalibrate with more data |
| Misclassifies single as multiple | Threshold too low | (Already fixed in update) |
| Slow to detect people | Too few frames required | Check min_frames in pattern_detector.py |
| Too many false positives | Thresholds too low | Already increased in update |

---

## Monitor Confidence Trends

### Good System Behavior:
- Empty → moves consistently in 50-70 range
- Occupied → jumps to 60-75 range quickly
- Multi → reaches 65-80 range
- Transitions smooth with clear margins > 8

### Issues:
- Constant switching between states → margin < 3 (uncertain)
- Never reaches occupied > 55 → pattern training issue
- All scores < 35 → INITIALIZING (normal at startup)

---

## Technical Parameters Reference

```python
# Thresholds (in pattern_detector.py)
self.min_confidence = 55.0      # ↑ Stricter (was 45)
self.min_margin = 8.0           # ↑ Stricter (was 3)
self.min_binary_margin = 5.0    # ↑ Stricter (was 2)

# Feature Weights (higher = more important)
estd (variance): 3.0            # ↑ Key for occupancy
mv_mean (temporal dynamics): 3.5 # ↑ Highest - captures movement
mv_max (peak dynamics): 3.5      # ↑ Highest
spec_entropy: 2.5                # Moderate

# Exponential decay
similarity = exp(-1.2 * spread)  # ↑ Stricter (was -0.75)
```

---

## Next Steps
1. ✅ Browser refresh to load updated code
2. ✅ Test all scenarios in "Live Data & Detection" page
3. ✅ Monitor detection_margin in API responses
4. 📋 Report any persistent false positives/negatives
5. 📈 Re-calibrate baseline patterns if needed (collect more data)
