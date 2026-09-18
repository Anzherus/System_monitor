"""Главный файл System Monitor - консольное приложение для мониторинга серверов"""
import logging, os, sys
from config import Settings, ensure_dirs
from modules.servers import ServerManager
from modules.logs import LogManager
from modules.benchmark import run_benchmark
from modules.generator import generate_infrastructure
from modules.ui import (
    menu_servers, menu_logs, menu_settings, 
    menu_statistics, menu_reports, run_analysis
)

# Загрузка настроек
settings = Settings.load()
ensure_dirs(settings)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(settings.logs_path, "application.log"),
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("system_monitor")


def main() -> None:
    """Главная функция приложения"""
    logger.info("Приложение запущено")
    
    # Инициализация менеджеров
    sm = ServerManager(settings)
    lm = LogManager(settings.logs_path)
    
    # Загрузка данных
    sm.load()
    
    # Состояние приложения
    state = {"records": [], "numeric": {}, "anomalies": []}
    
    # Главное меню
    while True:
        print("\n" + "=" * 60)
        print("SYSTEM MONITOR".center(60))
        print("=" * 60)
        print("1. Серверы")
        print("2. Логи")
        print("3. Анализ")
        print("4. Статистика")
        print("5. Аномалии")
        print("6. Отчеты")
        print("7. Генерация тестовых данных")
        print("8. Бенчмарк производительности")
        print("9. Настройки")
        print("0. Выход")
        
        choice = input("\n> ").strip()
        
        if choice == "0":
            logger.info("Приложение завершено")
            print("\nДо свидания!")
            return
        
        elif choice == "1":
            menu_servers(sm)
        
        elif choice == "2":
            menu_logs(lm)
        
        elif choice == "3":
            state["records"], state["numeric"], state["anomalies"] = run_analysis(sm, lm, settings)
        
        elif choice == "4":
            if not state["records"]:
                print("\nСначала выполните Анализ.")
            else:
                menu_statistics(state["records"], state["numeric"], state["anomalies"], sm)
        
        elif choice == "5":
            if not state["records"]:
                print("\nСначала выполните Анализ.")
            else:
                print(f"\nАномалий обнаружено: {len(state['anomalies'])}")
                for i, a in enumerate(state["anomalies"][:30], 1):
                    print(f"{i}. Сервер: {a['server']}, Метрика: {a['metric']}, "
                          f"Значение: {a['value']}, Z-оценка: {a['z_score']}")
        
        elif choice == "6":
            if not state["records"]:
                print("\nСначала выполните Анализ.")
            else:
                menu_reports(state["records"], state["numeric"], state["anomalies"], sm, settings)
        
        elif choice == "7":
            try:
                n_srv = int(input(f"\nСерверов [{settings.test_servers}]: ") or settings.test_servers)
                n_log = int(input(f"Логов [{settings.test_logs}]: ") or settings.test_logs)
                generate_infrastructure(settings, n_srv, n_log)
                sm.load()
                print("\nТестовые данные сгенерированы.")
            except ValueError:
                print("\nНеверное число.")
        
        elif choice == "8":
            run_benchmark(settings)
        
        elif choice == "9":
            menu_settings(settings)
        
        else:
            print("\nНеизвестная опция.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nПрограмма прервана пользователем.")
        logger.info("Программа прервана пользователем")
    except Exception as e:
        logger.error("Критическая ошибка: %s", e)
        print(f"\nПроизошла ошибка: {e}")
        sys.exit(1)