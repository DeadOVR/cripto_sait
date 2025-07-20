from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Numeric, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'test'


# Настройка базы данных
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    login = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)


class MiningRecord(Base):
    __tablename__ = 'mining_records'
    id = Column(Integer, primary_key=True)
    username = Column(String(50))
    email = Column(String(255))
    cryptocurrency = Column(String(50), nullable=False)
    amount = Column(Numeric(20, 10), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# Подключение к PostgreSQL
DATABASE_URL = 'postgresql+psycopg2://postgres:12345678@localhost:5432/testshop'
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/home')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        login = request.form['login']
        password = request.form['password']
        email = request.form['email']

        db_session = Session()
        try:
            hashed_password = generate_password_hash(password)
            new_user = User(
                username=username,
                login=login,
                password=hashed_password,
                email=email
            )
            db_session.add(new_user)
            db_session.commit()
            flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
            return redirect(url_for('home'))
        except IntegrityError as e:
            db_session.rollback()
            if 'username' in str(e):
                flash('Это имя пользователя уже занято', 'error')
            elif 'login' in str(e):
                flash('Этот логин уже используется', 'error')
            elif 'email' in str(e):
                flash('Этот email уже зарегистрирован', 'error')
            else:
                flash('Ошибка при регистрации', 'error')
        finally:
            db_session.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']

        db_session = Session()
        try:
            user = db_session.query(User).filter_by(login=login).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['username'] = user.username
                flash('Вы успешно вошли в систему!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Неверный логин или пароль', 'error')
        finally:
            db_session.close()

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Пожалуйста, войдите в систему', 'error')
        return redirect(url_for('login'))

    db_session = Session()
    try:
        user = db_session.query(User).get(session['user_id'])
        # Фильтруем по username вместо user_id
        mining_records = db_session.query(MiningRecord).filter_by(
            username=user.username
        ).order_by(
            MiningRecord.created_at.desc()
        ).all()

        return render_template('dashboard.html',
                               username=user.username,
                               mining_records=mining_records)
    finally:
        db_session.close()


@app.route('/save_mining', methods=['POST'])
def save_mining():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    db_session = Session()
    try:
        user = db_session.query(User).get(session['user_id'])

        # Создаем запись без user_id
        record = MiningRecord(
            username=user.username,
            email=user.email,
            cryptocurrency=data['cryptocurrency'],
            amount=float(data['amount'])
        )
        db_session.add(record)
        db_session.commit()

        # Обновляем запрос для подсчета суммы (теперь фильтруем по username)
        total_amount = db_session.query(
            func.sum(MiningRecord.amount)
        ).filter_by(
            username=user.username,
            cryptocurrency=data['cryptocurrency']
        ).scalar() or 0

        return jsonify({
            'success': True,
            'username': user.username,
            'total_amount': float(total_amount)
        })
    except Exception as e:
        db_session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db_session.close()


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)