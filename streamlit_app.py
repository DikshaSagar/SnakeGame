import streamlit as st
import numpy as np
import random
import time

try:
    import cv2
    import mediapipe as mp
    from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, RTCConfiguration
    import av
    WEBRTC_AVAILABLE = True
except ImportError as e:
    WEBRTC_AVAILABLE = False
    st.error(f"Import error: {e}")

# Page config
st.set_page_config(
    page_title="🐍 Hand Gesture Snake Game",
    page_icon="🎮",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .stButton>button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        font-size: 18px;
        padding: 12px;
        border-radius: 8px;
        border: none;
        cursor: pointer;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

if not WEBRTC_AVAILABLE:
    st.error("""
    ### ⚠️ WebRTC Not Available
    
    Some required packages couldn't be loaded. 
    
    **Alternative:** Try the HTML version (`snake_game_web.html`) which works in any browser without deployment issues!
    
    Deploy it on:
    - **Netlify Drop**: https://app.netlify.com/drop (easiest - just drag and drop!)
    - **GitHub Pages**: Upload as index.html
    """)
    st.info("The HTML version is actually better for games - faster, more compatible, and works on mobile!")
    st.stop()

class SnakeGame:
    def __init__(self):
        self.width = 640
        self.height = 480
        self.grid_size = 20
        self.game_speed = 0.12
        
        self.reset_game()
        
        # Hand tracking
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
            max_num_hands=1
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        self.last_direction_change = time.time()
        self.direction_cooldown = 0.15
        self.last_update = time.time()
    
    def reset_game(self):
        self.snake = [(self.width // 2, self.height // 2)]
        self.direction = (self.grid_size, 0)
        self.food = self.generate_food()
        self.score = 0
        self.game_over = False
        self.last_update = time.time()
    
    def generate_food(self):
        while True:
            food_x = random.randint(0, (self.width - self.grid_size) // self.grid_size) * self.grid_size
            food_y = random.randint(0, (self.height - self.grid_size) // self.grid_size) * self.grid_size
            food_pos = (food_x, food_y)
            if food_pos not in self.snake:
                return food_pos
    
    def get_hand_direction(self, hand_landmarks, frame_shape):
        index_finger_tip = hand_landmarks.landmark[8]
        
        h, w = frame_shape[:2]
        finger_x = int(index_finger_tip.x * w)
        finger_y = int(index_finger_tip.y * h)
        
        head_x, head_y = self.snake[0]
        
        dx = finger_x - head_x
        dy = finger_y - head_y
        
        dead_zone = 40
        
        if abs(dx) > abs(dy) and abs(dx) > dead_zone:
            new_direction = (self.grid_size, 0) if dx > 0 else (-self.grid_size, 0)
        elif abs(dy) > abs(dx) and abs(dy) > dead_zone:
            new_direction = (0, self.grid_size) if dy > 0 else (0, -self.grid_size)
        else:
            return self.direction
        
        if (new_direction[0] * -1, new_direction[1] * -1) == self.direction:
            return self.direction
        
        return new_direction
    
    def update(self):
        if self.game_over:
            return
        
        current_time = time.time()
        if current_time - self.last_update < self.game_speed:
            return
        
        self.last_update = current_time
        
        head_x, head_y = self.snake[0]
        new_head = (head_x + self.direction[0], head_y + self.direction[1])
        
        if (new_head[0] < 0 or new_head[0] >= self.width or
            new_head[1] < 0 or new_head[1] >= self.height or
            new_head in self.snake[1:]):
            self.game_over = True
            return
        
        self.snake.insert(0, new_head)
        
        if new_head == self.food:
            self.score += 10
            self.food = self.generate_food()
        else:
            self.snake.pop()
    
    def draw(self, frame):
        # Draw snake
        for i, segment in enumerate(self.snake):
            color = (0, 255, 100) if i == 0 else (0, 200, 0)
            cv2.rectangle(
                frame,
                segment,
                (segment[0] + self.grid_size - 2, segment[1] + self.grid_size - 2),
                color,
                -1
            )
            # Draw border
            cv2.rectangle(
                frame,
                segment,
                (segment[0] + self.grid_size - 2, segment[1] + self.grid_size - 2),
                (0, 150, 0),
                1
            )
        
        # Draw food
        food_center = (self.food[0] + self.grid_size // 2, self.food[1] + self.grid_size // 2)
        cv2.circle(frame, food_center, self.grid_size // 2, (0, 0, 255), -1)
        cv2.circle(frame, (food_center[0]-3, food_center[1]-3), 3, (100, 100, 255), -1)
        
        # Draw score
        cv2.putText(frame, f'Score: {self.score}', (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        if self.game_over:
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (self.width, self.height), (0, 0, 0), -1)
            frame = cv2.addWeighted(frame, 0.5, overlay, 0.5, 0)
            cv2.putText(frame, 'GAME OVER!', (self.width // 2 - 150, self.height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
        
        return frame

# Initialize session state
if 'game' not in st.session_state:
    st.session_state.game = SnakeGame()
    st.session_state.high_score = 0

class VideoProcessor(VideoProcessorBase):
    def __init__(self):
        self.game = st.session_state.game
    
    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        img = cv2.flip(img, 1)
        
        rgb_frame = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.game.hands.process(rgb_frame)
        
        if results.multi_hand_landmarks and not self.game.game_over:
            for hand_landmarks in results.multi_hand_landmarks:
                self.game.mp_draw.draw_landmarks(
                    img, hand_landmarks, self.game.mp_hands.HAND_CONNECTIONS
                )
                
                current_time = time.time()
                if current_time - self.game.last_direction_change > self.game.direction_cooldown:
                    new_direction = self.game.get_hand_direction(hand_landmarks, img.shape)
                    if new_direction != self.game.direction:
                        self.game.direction = new_direction
                        self.game.last_direction_change = current_time
        
        self.game.update()
        img = self.game.draw(img)
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")

# UI
st.title("🎮 Hand Gesture Snake Game 🐍")
st.markdown("### Control with your hand movements!")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
        <div class="metric-card">
            <h3>Score</h3>
            <h1 style="color: #4CAF50;">{st.session_state.game.score}</h1>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
        <div class="metric-card">
            <h3>High Score</h3>
            <h1 style="color: #ff6b6b;">{st.session_state.high_score}</h1>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
        <div class="metric-card">
            <h3>Length</h3>
            <h1 style="color: #4ecdc4;">{len(st.session_state.game.snake)}</h1>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

col_game, col_controls = st.columns([2, 1])

with col_game:
    rtc_configuration = RTCConfiguration(
        {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
    )
    
    webrtc_ctx = webrtc_streamer(
        key="snake-game",
        video_processor_factory=VideoProcessor,
        rtc_configuration=rtc_configuration,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
    )

with col_controls:
    st.markdown("### 🎯 How to Play")
    st.info("""
    1. **Show your hand** to camera
    2. **Point index finger** to control
    3. **Eat red food** to grow
    4. **Avoid walls** and tail
    """)
    
    if st.button("🔄 Restart Game", use_container_width=True):
        if st.session_state.game.score > st.session_state.high_score:
            st.session_state.high_score = st.session_state.game.score
        st.session_state.game.reset_game()
        st.rerun()
    
    if st.session_state.game.game_over:
        st.error("💀 Game Over!")
        st.metric("Final Score", st.session_state.game.score)

st.markdown("---")
st.markdown("""
<div style="text-align: center; opacity: 0.7;">
    Made with ❤️ using Python, OpenCV & MediaPipe
</div>
""", unsafe_allow_html=True)
