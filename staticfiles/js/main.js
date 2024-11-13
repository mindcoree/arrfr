class FinBot {
    constructor() {
        this.chatContainer = document.getElementById('chatContainer');
        this.quizContainer = document.getElementById('quizContainer');
        this.registrationModal = new bootstrap.Modal(document.getElementById('registrationModal'));
        
        this.initializeEventListeners();
        this.checkRegistration();
    }

    initializeEventListeners() {
        // Обработчики тем
        document.querySelectorAll('.topic-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleTopic(e));
        });

        // Обработчик викторины
        document.getElementById('startQuiz')?.addEventListener('click', () => this.startQuiz());
    }

    async checkRegistration() {
        try {
            const response = await fetch('/api/registration/check/');
            const data = await response.json();
            
            if (!data.is_registered) {
                this.showRegistrationForm(data.next_step);
            }
        } catch (error) {
            console.error('Error checking registration:', error);
        }
    }

    async handleTopic(e) {
        const topic = e.target.dataset.topic;
        
        try {
            const response = await fetch('/api/topic/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({ topic })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.addMessage(data.response);
                this.updateProfile(data.used_functions);
            } else {
                this.showError(data.message);
            }
        } catch (error) {
            console.error('Error handling topic:', error);
            this.showError('Произошла ошибка при обработке темы');
        }
    }

    async startQuiz() {
        try {
            const response = await fetch('/api/quiz/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({ action: 'start' })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.showQuiz(data);
            } else {
                this.showError(data.message);
            }
        } catch (error) {
            console.error('Error starting quiz:', error);
            this.showError('Произошла ошибка при запуске викторины');
        }
    }

    addMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message';
        messageDiv.textContent = text;
        this.chatContainer.appendChild(messageDiv);
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
    }

    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger';
        errorDiv.textContent = message;
        this.chatContainer.appendChild(errorDiv);
    }

    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    new FinBot();
}); 