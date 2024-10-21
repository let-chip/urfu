import telebot
from telebot import types
import json
import schedule
import time
import threading
import logging

TOKEN = '7264109335:AAFKWF8IampwKf2WspdOgu1WcD0umRtLJrg'
data_file = 'tasks.json'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TaskBot:
    def __init__(self, token, data_file):
        self.bot = telebot.TeleBot(token)
        self.data_file = data_file
        self.tasks = self.load_tasks()
        self.reminders = {}

        # Обработчики команд
        @self.bot.message_handler(commands=['start'])
        def start(message):
            self.start_command(message)

        @self.bot.message_handler(func=lambda message: message.text == "Добавить дело")
        def add_task(message):
            self.add_task_command(message)

        @self.bot.message_handler(func=lambda message: message.text == "Показать дела")
        def show_tasks(message):
            self.show_tasks_command(message)

        @self.bot.message_handler(func=lambda message: message.text == "Удалить дело")
        def delete_task(message):
            self.delete_task_command(message)

        @self.bot.message_handler(func=lambda message: message.text == "Редактировать дело")
        def edit_task(message):
            self.edit_task_command(message)

        @self.bot.message_handler(func=lambda message: message.text == "Сортировать по времени")
        def sort_tasks(message):
            self.sort_tasks_command(message)

        @self.bot.message_handler(func=lambda message: message.text == "Напомнить")
        def set_reminder(message):
            self.set_reminder_command(message)

        @self.bot.message_handler(func=lambda message: message.text == "Удалить все дела")
        def clear_tasks(message):
            self.clear_tasks_command(message)

        # Запускаем планировщик в отдельном потоке
        scheduler_thread = threading.Thread(target=self.run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()

        self.bot.polling()

    def start_command(self, message):
        self.bot.send_message(message.chat.id, "Привет! 👋 Я бот-напоминалка. Давай составим список дел на сегодня! 😉")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Добавить дело"))
        markup.add(types.KeyboardButton("Показать дела"))
        markup.add(types.KeyboardButton("Удалить дело"))
        markup.add(types.KeyboardButton("Редактировать дело"))
        markup.add(types.KeyboardButton("Сортировать по времени"))
        markup.add(types.KeyboardButton("Напомнить"))
        markup.add(types.KeyboardButton("Удалить все дела"))
        self.bot.send_message(message.chat.id, "Что хочешь сделать?", reply_markup=markup)

    def add_task_command(self, message):
        self.bot.send_message(message.chat.id, "Введите ваше дело:")
        self.bot.register_next_step_handler(message, self.get_task_time)

    def get_task_time(self, message):
        user_id = message.from_user.id
        task = message.text
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Пропустить"))  # Добавляем кнопку "Пропустить"
        self.bot.send_message(message.chat.id, "Введите время выполнения дела в формате ЧЧ:ММ (например, 18:30) или нажмите 'Пропустить':", reply_markup=markup)
        self.bot.register_next_step_handler(message, self.save_task, task)

    def save_task(self, message, task):
        user_id = message.from_user.id
        time_str = message.text
        if time_str.lower() == 'пропустить':
            time_str = ''
        else:
            try:
                hour, minute = map(int, time_str.split(':'))
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    time_str = f"{hour:02d}:{minute:02d}"
                else:
                    self.bot.send_message(message.chat.id, "Некорректное время. Введите время в формате ЧЧ:ММ.")
                    self.get_task_time(message)
                    return
            except ValueError:
                self.bot.send_message(message.chat.id, "Некорректный формат времени. Введите время в формате ЧЧ:ММ.")
                self.get_task_time(message)
                return

        if user_id in self.tasks:
            self.tasks[user_id].append({'task': task, 'time': time_str})
        else:
            self.tasks[user_id] = [{'task': task, 'time': time_str}]
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.tasks, f)
            self.bot.send_message(message.chat.id, "Дело добавлено! 👍")
            self.start_command(message)  # Вернем кнопки главного меню
        except json.JSONDecodeError:
            self.bot.send_message(message.chat.id, "Ошибка при записи данных в файл. Попробуйте снова.")
            self.start_command(message)  # Вернем кнопки главного меню
        except Exception as e:
            self.bot.send_message(message.chat.id, f"Произошла ошибка при сохранении: {e}")
            self.start_command(message)  # Вернем кнопки главного меню

    def show_tasks_command(self, message):
        user_id = message.from_user.id
        if user_id in self.tasks and self.tasks[user_id]:
            task_list = []
            for i, item in enumerate(self.tasks[user_id]):
                time_str = item.get('time', '')
                if time_str:
                    task_list.append(f"{i+1}. {item['task']} ({time_str})")
                else:
                    task_list.append(f"{i+1}. {item['task']}")
            self.bot.send_message(message.chat.id, f"Ваши дела на сегодня:\n{'\n'.join(task_list)}")
        else:
            self.bot.send_message(message.chat.id, "У вас пока нет дел.")

    def delete_task_command(self, message):
        user_id = message.from_user.id
        if user_id in self.tasks and self.tasks[user_id]:
            self.bot.send_message(message.chat.id, "Введите номер дела, которое хотите удалить:")
            self.bot.register_next_step_handler(message, self.process_delete_task)
        else:
            self.bot.send_message(message.chat.id, "У вас пока нет дел.")

    def process_delete_task(self, message):
        user_id = message.from_user.id
        try:
            task_index = int(message.text) - 1
            if 0 <= task_index < len(self.tasks[user_id]):
                deleted_task = self.tasks[user_id].pop(task_index)
                try:
                    with open(self.data_file, 'w') as f:
                        json.dump(self.tasks, f)
                    self.bot.send_message(message.chat.id, f"Дело '{deleted_task['task']}' удалено.")
                    self.start_command(message)
                except json.JSONDecodeError:
                    self.bot.send_message(message.chat.id, "Ошибка при записи данных в файл. Попробуйте снова.")
                    self.start_command(message)
                except Exception as e:
                    self.bot.send_message(message.chat.id, f"Произошла ошибка при сохранении: {e}")
                    self.start_command(message)
            else:
                self.bot.send_message(message.chat.id, "Некорректный номер дела.")
                self.start_command(message)
        except ValueError:
            self.bot.send_message(message.chat.id, "Введите номер дела цифрами.")
            self.start_command(message)

    def edit_task_command(self, message):
        user_id = message.from_user.id
        if user_id in self.tasks and self.tasks[user_id]:
            self.bot.send_message(message.chat.id, "Введите номер дела, которое хотите отредактировать:")
            self.bot.register_next_step_handler(message, self.process_edit_task)
        else:
            self.bot.send_message(message.chat.id, "У вас пока нет дел.")

    def process_edit_task(self, message):
        user_id = message.from_user.id
        try:
            task_index = int(message.text) - 1
            if 0 <= task_index < len(self.tasks[user_id]):
                self.bot.send_message(message.chat.id, "Введите новый текст дела:")
                self.bot.register_next_step_handler(message, self.update_task, user_id, task_index)
            else:
                self.bot.send_message(message.chat.id, "Некорректный номер дела.")
                self.start_command(message)
        except ValueError:
            self.bot.send_message(message.chat.id, "Введите номер дела цифрами.")
            self.start_command(message)

    def update_task(self, message, user_id, task_index):
        new_task = message.text
        self.tasks[user_id][task_index]['task'] = new_task
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.tasks, f)
            self.bot.send_message(message.chat.id, "Дело обновлено! 👍")
            self.start_command(message)
        except json.JSONDecodeError:
            self.bot.send_message(message.chat.id, "Ошибка при записи данных в файл. Попробуйте снова.")
            self.start_command(message)
        except Exception as e:
            self.bot.send_message(message.chat.id, f"Произошла ошибка при сохранении: {e}")
            self.start_command(message)

    def sort_tasks_command(self, message):
        user_id = message.from_user.id
        if user_id in self.tasks and self.tasks[user_id]:
            sorted_tasks = sorted(self.tasks[user_id], key=lambda item: item.get('time', '23:59'))
            self.tasks[user_id] = sorted_tasks
            try:
                with open(self.data_file, 'w') as f:
                    json.dump(self.tasks, f)
                self.bot.send_message(message.chat.id, "Дела отсортированы по времени! 👍")
                self.start_command(message)
            except json.JSONDecodeError:
                self.bot.send_message(message.chat.id, "Ошибка при записи данных в файл. Попробуйте снова.")
                self.start_command(message)
            except Exception as e:
                self.bot.send_message(message.chat.id, f"Произошла ошибка при сохранении: {e}")
                self.start_command(message)
        else:
            self.bot.send_message(message.chat.id, "У вас пока нет дел.")
            self.start_command(message)

    def set_reminder_command(self, message):
        user_id = message.from_user.id
        self.bot.send_message(message.chat.id, "Введите дело, о котором хотите напомнить:")
        self.bot.register_next_step_handler(message, self.get_reminder_task)
    def get_reminder_task(self, message):
        user_id = message.from_user.id
        task = message.text
        self.bot.send_message(message.chat.id, "Введите время напоминания в формате ЧЧ:ММ (например, 18:30):")
        self.bot.register_next_step_handler(message, self.get_reminder_time, task)

    def get_reminder_time(self, message, task):
        user_id = message.from_user.id
        try:
            reminder_time = message.text.split(':')
            hour = int(reminder_time[0])
            minute = int(reminder_time[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                schedule.every().day.at(message.text).do(self.send_reminder, user_id, task)
                self.reminders[user_id] = self.reminders.get(user_id, []) + [(task, message.text)]
                self.bot.send_message(message.chat.id, f"Напоминание о '{task}' установлено на {message.text}.")
                self.start_command(message)
            else:
                self.bot.send_message(message.chat.id, "Некорректное время. Введите время в формате ЧЧ:ММ.")
                self.start_command(message)
        except ValueError:
            self.bot.send_message(message.chat.id, "Некорректный формат времени. Введите время в формате ЧЧ:ММ.")
            self.start_command(message)

    def send_reminder(self, user_id, task):
        self.bot.send_message(user_id, f"Напоминание: {task}")

    def clear_tasks_command(self, message):
        user_id = message.from_user.id
        if user_id in self.tasks:
            self.tasks[user_id] = []
            self.save_tasks()
            self.bot.send_message(message.chat.id, "Все дела удалены! 👍")
            self.start_command(message)
        else:
            self.bot.send_message(message.chat.id, "У вас пока нет дел.")
            self.start_command(message)

    def run_scheduler(self):
        while True:
            schedule.run_pending()
            time.sleep(1)

    def load_tasks(self):
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.info("Файл с задачами не найден. Создаю новый.")
            return {}
        except json.JSONDecodeError:
            logging.error("Ошибка в формате файла с задачами. Создаю новый.")
            return {}
        except Exception as e:
            logging.error(f"Произошла ошибка при загрузке данных: {e}")
            return {}

    def save_tasks(self):
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.tasks, f)
        except json.JSONDecodeError:
            logging.error("Ошибка при записи данных в файл. Попробуйте снова.")
        except Exception as e:
            logging.error(f"Произошла ошибка при сохранении: {e}")

if __name__ == '__main__':
    bot = TaskBot(TOKEN, data_file)
#'7264109335:AAFKWF8IampwKf2WspdOgu1WcD0umRtLJrg'