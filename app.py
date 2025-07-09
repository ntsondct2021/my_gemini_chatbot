import google.generativeai as genai
import os
import sys
from flask import Flask, request, render_template_string

app = Flask(__name__)

# --- Cấu hình Khóa API Gemini của bạn ---
# Đảm bảo khóa API được thiết lập trong biến môi trường trên máy chủ
# Hoặc bạn sẽ cần cơ chế an toàn khác để quản lý nó
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("Lỗi: Không tìm thấy khóa API GOOGLE_API_KEY trong biến môi trường.")
    sys.exit(1) # Thoát nếu không có khóa API để tránh lỗi khi deploy

genai.configure(api_key=GOOGLE_API_KEY)

# --- Chọn và Khởi tạo Mô hình Gemini ---
# Chúng ta vẫn sẽ cố gắng sử dụng gemini-pro
MODEL_NAME = 'models/gemini-2.5-flash'
model = None # Khởi tạo biến model

try:
    # Kiểm tra các mô hình có sẵn nếu MODEL_NAME không hoạt động
    # Chỉ thực hiện kiểm tra này khi ứng dụng khởi động
    found_model = False
    for m in genai.list_models():
        if m.name == MODEL_NAME and 'generateContent' in m.supported_generation_methods:
            found_model = True
            break
    
    if found_model:
        model = genai.GenerativeModel(MODEL_NAME)
    else:
        # Nếu gemini-pro không có, hãy thử tìm mô hình khác có thể sử dụng
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                MODEL_NAME = m.name # Cập nhật tên mô hình
                model = genai.GenerativeModel(MODEL_NAME)
                print(f"Cảnh báo: '{MODEL_NAME}' không khả dụng, sử dụng '{MODEL_NAME}' thay thế.")
                break
        if model is None:
            raise Exception("Không tìm thấy mô hình Gemini nào phù hợp hỗ trợ 'generateContent'.")

except Exception as e:
    print(f"Lỗi khi khởi tạo mô hình Gemini: {e}")
    sys.exit(1)

# Lịch sử trò chuyện cho phiên hiện tại (đơn giản, không lưu trữ giữa các request)
# Đối với chatbot trực tuyến, bạn thường cần một cơ chế lưu trữ bền vững hơn (ví dụ: cơ sở dữ liệu)
# hoặc quản lý lịch sử theo session của người dùng. Với ví dụ này, mỗi lần gửi tin nhắn là một request mới.
# Vì vậy, chúng ta sẽ bắt đầu một phiên trò chuyện mới cho mỗi tin nhắn để giữ ví dụ đơn giản.

# HTML cho giao diện web đơn giản
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chatbot TinhocDCT của bạn</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; color: #333; }
        .chat-container { max-width: 600px; margin: auto; background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        .message-box { height: 300px; overflow-y: scroll; border: 1px solid #ddd; padding: 10px; margin-bottom: 15px; border-radius: 4px; background-color: #e9e9e9; }
        .user-message { text-align: right; color: #007bff; }
        .bot-message { text-align: left; color: #28a745; }
        input[type="text"] { width: calc(100% - 70px); padding: 10px; border: 1px solid #ddd; border-radius: 4px; margin-right: 10px; }
        button { padding: 10px 15px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background-color: #0056b3; }
    </style>
</head>
<body>
    <div class="chat-container">
        <h1>Chatbot TinhocDCT</h1>
        <div class="message-box" id="messageBox">
            <div class="bot-message"><strong>Chatbot:</strong> Xin chào! Tôi có thể giúp gì cho bạn?</div>
        </div>
        <form id="chatForm" onsubmit="sendMessage(event)">
            <input type="text" id="userInput" placeholder="Nhập tin nhắn của bạn..." autocomplete="off">
            <button type="submit">Gửi</button>
        </form>
    </div>

    <script>
        // Lấy lịch sử tin nhắn từ Local Storage hoặc khởi tạo nếu chưa có
        let chatHistory = JSON.parse(localStorage.getItem('geminiChatHistory')) || [];

        // Hàm hiển thị tin nhắn trong hộp chat
        function displayMessage(sender, message) {
            const messageBox = document.getElementById('messageBox');
            const msgDiv = document.createElement('div');
            msgDiv.classList.add(sender === 'user' ? 'user-message' : 'bot-message');
            msgDiv.innerHTML = `<strong>${sender === 'user' ? 'Bạn' : 'Chatbot'}:</strong> ${message}`;
            messageBox.appendChild(msgDiv);
            messageBox.scrollTop = messageBox.scrollHeight; // Cuộn xuống dưới cùng
        }

        // Tải lại lịch sử khi trang được tải
        window.onload = function() {
            chatHistory.forEach(msg => displayMessage(msg.sender, msg.message));
        };

        async function sendMessage(event) {
            event.preventDefault(); // Ngăn chặn form submit truyền thống
            const userInput = document.getElementById('userInput');
            const message = userInput.value.trim();

            if (message === '') return;

            displayMessage('user', message);
            chatHistory.push({ sender: 'user', message: message });
            localStorage.setItem('geminiChatHistory', JSON.stringify(chatHistory));

            userInput.value = ''; // Xóa input

            // Gửi tin nhắn đến Flask backend
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message: message, history: chatHistory }), // Gửi cả lịch sử
                });
                const data = await response.json();
                displayMessage('bot', data.response);
                chatHistory.push({ sender: 'bot', message: data.response });
                localStorage.setItem('geminiChatHistory', JSON.stringify(chatHistory));

            } catch (error) {
                console.error('Lỗi khi gửi tin nhắn:', error);
                displayMessage('bot', 'Xin lỗi, đã xảy ra lỗi. Vui lòng thử lại.');
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    # Lấy lịch sử từ frontend để duy trì ngữ cảnh
    # Chuyển đổi lịch sử từ JSON sang định dạng phù hợp cho Gemini
    # Đảm bảo 'role' và 'parts' đúng định dạng
    history_from_frontend = request.json.get('history', [])
    gemini_history = []
    for msg in history_from_frontend:
        role = 'user' if msg['sender'] == 'user' else 'model'
        gemini_history.append({'role': role, 'parts': [{'text': msg['message']}]})
    
    # Bắt đầu cuộc trò chuyện với lịch sử được cung cấp
    chat_session = model.start_chat(history=gemini_history)

    try:
        response = chat_session.send_message(user_message)
        return {'response': response.text}
    except Exception as e:
        return {'response': f"Xin lỗi, đã xảy ra lỗi từ API: {e}"}, 500

if __name__ == '__main__':
    # Chạy ứng dụng Flask trên máy tính của bạn để kiểm tra
    app.run(debug=True, host='0.0.0.0', port=5000)
