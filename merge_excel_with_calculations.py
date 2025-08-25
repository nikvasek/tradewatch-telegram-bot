import pandas as pd
import os
import glob
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule
from datetime import datetime
import config
from tradewatch_login import process_supplier_file_with_tradewatch

def format_ean_to_13_digits(ean_value):
    """
    Приводит EAN к стандартному 13-цифровому формату
    """
    if pd.isna(ean_value):
        return None
    
    try:
        # Конвертируем в строку и удаляем пробелы
        ean_str = str(ean_value).strip()
        
        # Если получилось пустое значение, возвращаем None
        if not ean_str:
            return None
        
        # Особая обработка для научной нотации
        if 'E' in ean_str.upper() or 'e' in ean_str:
            try:
                # Конвертируем через float для обработки научной нотации
                ean_float = float(ean_str)
                ean_str = str(int(ean_float))
            except:
                pass
        
        # Удаляем все нечисловые символы
        ean_digits = ''.join(char for char in ean_str if char.isdigit())
        
        # Если получилось пустое значение, возвращаем None
        if not ean_digits:
            return None
            
        # Обрезаем до 13 цифр если больше
        if len(ean_digits) > 13:
            ean_digits = ean_digits[:13]
            
        # Дополняем ведущими нулями до 13 цифр
        ean_formatted = ean_digits.zfill(13)
        
        return ean_formatted
        
    except Exception as e:
        print(f"Ошибка при форматировании EAN {ean_value}: {str(e)}")
        return None

def create_hyperlinks(df):
    """
    Создает гиперссылки в колонке Link на основе номеров из колонок минимальной цены
    """
    # Ищем колонку с номерами для ссылок
    link_number_column = None
    for col in config.LINK_NUMBER_COLUMNS:
        if col in df.columns:
            link_number_column = col
            break
    
    if link_number_column is None:
        print("Не найдена колонка с номерами для создания ссылок")
        return df
    
    # Создаем или обновляем колонку Link
    if 'Link' not in df.columns:
        df['Link'] = ''
    
    # Конвертируем колонку Link в строковый тип
    df['Link'] = df['Link'].astype(str)
    
    # Создаем гиперссылки
    for index, row in df.iterrows():
        link_number = row[link_number_column]
        if pd.notna(link_number) and str(link_number).strip():
            # Извлекаем номер из ссылки если это уже ссылка
            if str(link_number).startswith('http'):
                # Если уже есть ссылка, извлекаем номер
                try:
                    number = str(link_number).split('/')[-1]
                    # Убираем .0 из номера если он есть
                    if number.endswith('.0'):
                        number = number[:-2]
                    df.at[index, 'Link'] = f"{config.ALLEGRO_BASE_URL}{number}"
                except:
                    df.at[index, 'Link'] = str(link_number)
            else:
                # Создаем новую ссылку
                # Конвертируем в число и обратно в строку для удаления .0
                try:
                    # Пытаемся конвертировать в число
                    clean_number = str(int(float(link_number)))
                except (ValueError, TypeError):
                    # Если не удается конвертировать, просто удаляем .0
                    clean_number = str(link_number).rstrip('.0')
                    if clean_number == '':
                        clean_number = '0'
                
                df.at[index, 'Link'] = f"{config.ALLEGRO_BASE_URL}{clean_number}"
    
    print(f"Созданы гиперссылки на основе колонки: {link_number_column}")
    return df

def create_product_links(df):
    """
    Создает гиперссылки в колонке Product Link на основе EAN кодов
    ТОЛЬКО если в DataFrame уже есть колонка Product Link
    """
    # Проверяем наличие колонки EAN
    if 'EAN' not in df.columns:
        print("Колонка EAN не найдена, пропускаем создание Product Link")
        return df
    
    # Проверяем наличие колонки Product Link в исходных данных
    if 'Product Link' not in df.columns:
        print("Колонка Product Link не найдена в прайсе поставщика, пропускаем создание гиперссылок")
        return df
    
    print("Найдена колонка Product Link в прайсе поставщика, создаем гиперссылки...")
    
    # Конвертируем колонку Product Link в строковый тип
    df['Product Link'] = df['Product Link'].astype(str)
    
    # Создаем гиперссылки на основе EAN
    for index, row in df.iterrows():
        ean_value = row['EAN']
        if pd.notna(ean_value) and str(ean_value).strip():
            # Форматируем EAN в 13-цифровой формат
            formatted_ean = format_ean_to_13_digits(ean_value)
            if formatted_ean:
                # Создаем URL с EAN
                product_url = f"https://api.qogita.com/variants/link/{formatted_ean}/"
                df.at[index, 'Product Link'] = product_url
    
    print("Созданы Product Link гиперссылки на основе EAN кодов")
    return df

def calculate_profit_and_roi(df):
    """
    Добавляет колонки Profit и ROI для расчета в Excel формулами
    """
    # Добавляем пустые колонки для Profit и ROI
    # Формулы будут добавлены при форматировании Excel
    if 'Profit' not in df.columns:
        df['Profit'] = None
    if 'ROI' not in df.columns:
        df['ROI'] = None
    
    print("Добавлены колонки Profit и ROI для расчета формулами Excel")
    return df

def merge_excel_files_by_ean_with_calculations(directory_path='.'):
    """
    Объединяет файлы Excel по EAN коду с расчетом прибыли и ROI.
    """
    
    # Получаем все файлы TradeWatch
    tradewatch_files = glob.glob(os.path.join(directory_path, config.TRADEWATCH_FILE_PATTERN))
    
    if not tradewatch_files:
        print("Не найдены файлы, начинающиеся с 'TradeWatch'")
        return
    
    print(f"Найдено файлов TradeWatch: {len(tradewatch_files)}")
    for file in tradewatch_files:
        print(f"  - {os.path.basename(file)}")
    
    # Собираем все EAN коды из файлов TradeWatch
    all_ean_data = []
    
    for file_path in tradewatch_files:
        try:
            print(f"\nОбрабатываем файл: {os.path.basename(file_path)}")
            
            # Читаем лист "Produkty wg EAN"
            df = pd.read_excel(file_path, sheet_name=config.TRADEWATCH_SHEET_NAME)
            
            # Проверяем наличие колонки EAN
            if 'EAN' not in df.columns:
                print(f"  Колонка 'EAN' не найдена в файле {file_path}")
                print(f"  Доступные колонки: {list(df.columns)}")
                continue
            
            # Добавляем информацию об источнике
            df['source_file'] = os.path.basename(file_path)
            
            # Фильтруем только строки с валидными EAN
            df_clean = df[df['EAN'].notna()].copy()
            
            # Форматируем EAN в 13-цифровой формат
            df_clean['EAN'] = df_clean['EAN'].apply(format_ean_to_13_digits)
            
            # Убираем строки с невалидными EAN
            df_clean = df_clean[df_clean['EAN'].notna()].copy()
            
            # Форматируем EAN в 13-цифровом формате
            df_clean['EAN'] = df_clean['EAN'].apply(format_ean_to_13_digits)
            
            all_ean_data.append(df_clean)
            print(f"  Найдено EAN кодов: {len(df_clean)}")
            
        except Exception as e:
            print(f"Ошибка при обработке файла {file_path}: {str(e)}")
    
    if not all_ean_data:
        print("Не удалось извлечь данные из файлов TradeWatch")
        return
    
    # Объединяем все данные TradeWatch
    combined_tradewatch = pd.concat(all_ean_data, ignore_index=True)
    print(f"\nВсего уникальных EAN кодов из TradeWatch: {combined_tradewatch['EAN'].nunique()}")
    
    # Находим другие Excel файлы для объединения
    all_excel_files = glob.glob(os.path.join(directory_path, "*.xlsx"))
    
    # Исключаем файлы TradeWatch, временные файлы Excel и файлы результатов
    other_files = []
    
    for f in all_excel_files:
        filename = os.path.basename(f)
        if not any(filename.startswith(prefix) for prefix in config.EXCLUDED_FILE_PREFIXES):
            other_files.append(f)
    
    if not other_files:
        print("Не найдены другие Excel файлы для объединения")
        # Рассчитываем прибыль и ROI для данных TradeWatch
        combined_tradewatch = calculate_profit_and_roi(combined_tradewatch)
        
        # Добавляем колонку Price PL
        combined_tradewatch = add_price_pl_column(combined_tradewatch)
        
        # Создаем гиперссылки
        combined_tradewatch = create_hyperlinks(combined_tradewatch)
        
        # Создаем Product Link гиперссылки
        combined_tradewatch = create_product_links(combined_tradewatch)
        
        # Сохраняем только данные TradeWatch
        output_file = os.path.join(directory_path, config.OUTPUT_FILE_MERGED_TRADEWATCH)
        save_formatted_excel(combined_tradewatch, output_file)
        print(f"Сохранены данные TradeWatch в файл: {output_file}")
        return
    
    print(f"\nНайдено других Excel файлов: {len(other_files)}")
    for file in other_files:
        print(f"  - {os.path.basename(file)}")
    
    # Объединяем с другими файлами
    merged_results = []
    
    for other_file in other_files:
        try:
            print(f"\nОбъединяем с файлом: {os.path.basename(other_file)}")
            
            # Читаем файл (пробуем первый лист)
            other_df = pd.read_excel(other_file)
            
            # Ищем колонку с GTIN или EAN
            gtin_column = None
            
            for col in config.POSSIBLE_GTIN_COLUMNS:
                if col in other_df.columns:
                    gtin_column = col
                    break
            
            if gtin_column is None:
                print(f"  Не найдена колонка GTIN/EAN в файле {other_file}")
                print(f"  Доступные колонки: {list(other_df.columns)}")
                continue
            
            # Очищаем данные GTIN
            other_df_clean = other_df[other_df[gtin_column].notna()].copy()
            
            # Форматируем GTIN в 13-цифровой формат
            other_df_clean[gtin_column] = other_df_clean[gtin_column].apply(format_ean_to_13_digits)
            
            # Убираем строки с невалидными GTIN
            other_df_clean = other_df_clean[other_df_clean[gtin_column].notna()].copy()
            
            # Форматируем GTIN в 13-цифровом формате
            other_df_clean[gtin_column] = other_df_clean[gtin_column].apply(format_ean_to_13_digits)
            
            # Объединяем по EAN/GTIN
            merged = pd.merge(
                combined_tradewatch,
                other_df_clean,
                left_on='EAN',
                right_on=gtin_column,
                how='inner'  # Оставляем только совпадающие EAN
            )
            
            if len(merged) > 0:
                merged['merged_with'] = os.path.basename(other_file)
                merged_results.append(merged)
                print(f"  Найдено совпадений: {len(merged)}")
            else:
                print(f"  Совпадений не найдено")
                
        except Exception as e:
            print(f"Ошибка при объединении с файлом {other_file}: {str(e)}")
    
    # Сохраняем результаты
    if merged_results:
        # Объединяем все результаты
        final_result = pd.concat(merged_results, ignore_index=True)
        
        # Рассчитываем прибыль и ROI
        final_result = calculate_profit_and_roi(final_result)
        
        # Добавляем колонку Price PL
        final_result = add_price_pl_column(final_result)
        
        # Создаем гиперссылки
        final_result = create_hyperlinks(final_result)
        
        # Создаем Product Link гиперссылки
        final_result = create_product_links(final_result)
        
        # Упорядочиваем колонки в нужном порядке и оставляем только нужные
        
        # Определяем доступные колонки из желаемого порядка (оставляем только их)
        available_ordered_columns = [col for col in config.DESIRED_COLUMN_ORDER if col in final_result.columns]
        
        # Формируем финальный порядок колонок (только указанные в DESIRED_COLUMN_ORDER)
        final_column_order = available_ordered_columns
        
        # Переупорядочиваем DataFrame и оставляем только нужные колонки
        final_result = final_result[final_column_order]
        
        # Сохраняем в файл с форматированием
        output_file = os.path.join(directory_path, config.OUTPUT_FILE_WITH_CALCULATIONS)
        save_formatted_excel(final_result, output_file)
        
        # Подготавливаем статистику
        stats = {
            'total_rows': len(final_result),
            'unique_ean': final_result['EAN'].nunique() if 'EAN' in final_result.columns else 0,
            'files_processed': len(other_files),
            'output_file': output_file
        }
        
        print(f"\nРезультат сохранен в файл: {output_file}")
        print(f"Всего строк в результате: {stats['total_rows']}")
        print(f"Уникальных EAN кодов: {stats['unique_ean']}")
        print(f"Порядок колонок: {final_column_order}")
        
        return stats
    else:
        print("\nСовпадений не найдено, сохраняем только данные TradeWatch")
        # Рассчитываем прибыль и ROI для данных TradeWatch
        combined_tradewatch = calculate_profit_and_roi(combined_tradewatch)
        
        # Добавляем колонку Price PL
        combined_tradewatch = add_price_pl_column(combined_tradewatch)
        
        # Создаем гиперссылки
        combined_tradewatch = create_hyperlinks(combined_tradewatch)
        
        # Создаем Product Link гиперссылки
        combined_tradewatch = create_product_links(combined_tradewatch)
        
        output_file = os.path.join(directory_path, config.OUTPUT_FILE_TRADEWATCH_ONLY)
        save_formatted_excel(combined_tradewatch, output_file)
        print(f"Данные TradeWatch сохранены в файл: {output_file}")

def save_formatted_excel(df, output_file):
    """
    Сохраняет DataFrame в Excel с форматированием согласно конфигурации
    """
    try:
        # Сохраняем DataFrame в файл
        df.to_excel(output_file, index=False, startrow=config.EXCEL_TO_EXCEL_STARTROW)
        
        # Загружаем workbook для форматирования
        wb = load_workbook(output_file)
        ws = wb.active
        
        # Добавляем заголовки в первые строки
        for row_num, row_data in config.TITLE_ROWS.items():
            for col_letter, value in row_data.items():
                if value is not None:
                    cell = ws[f"{col_letter}{row_num}"]
                    cell.value = value
                    
                    # Применяем цвета и стили для заголовков
                    if col_letter in ['D', 'I']:  # Колонки с названиями
                        cell.font = Font(
                            name=config.TITLE_FONT_SETTINGS['name'],
                            size=config.TITLE_FONT_SETTINGS['size'],
                            bold=config.TITLE_FONT_SETTINGS['bold'],
                            color=config.TITLE_LABEL_FONT_COLOR
                        )
                    elif col_letter in ['G', 'M']:  # Колонки со значениями
                        cell.font = Font(
                            name=config.TITLE_FONT_SETTINGS['name'],
                            size=config.TITLE_FONT_SETTINGS['size'],
                            bold=config.TITLE_FONT_SETTINGS['bold'],
                            color=config.TITLE_VALUE_FONT_COLOR
                        )
        
        # Настраиваем заголовки таблицы
        header_row = config.EXCEL_HEADER_ROW_NUM
        ws.row_dimensions[header_row].height = config.EXCEL_HEADER_ROW_HEIGHT
        
        # Стили для заголовков
        header_font = Font(
            name=config.HEADER_FONT['name'],
            size=config.HEADER_FONT['size'],
            bold=config.HEADER_FONT['bold'],
            color=config.HEADER_FONT['color']
        )
        
        header_alignment = Alignment(
            horizontal=config.HEADER_ALIGNMENT['horizontal'],
            vertical=config.HEADER_ALIGNMENT['vertical'],
            wrap_text=config.HEADER_ALIGNMENT['wrap_text']
        )
        
        header_fill = PatternFill(
            start_color=config.HEADER_FILL['start_color'],
            end_color=config.HEADER_FILL['end_color'],
            fill_type=config.HEADER_FILL['fill_type']
        )
        
        # Стили для данных
        data_font = Font(
            name=config.DATA_FONT['name'],
            size=config.DATA_FONT['size']
        )
        
        # Выравнивание по умолчанию
        data_alignment = Alignment(
            horizontal=config.DATA_ALIGNMENT['horizontal'],
            vertical=config.DATA_ALIGNMENT['vertical']
        )
        
        # Выравнивание по правому краю
        data_alignment_right = Alignment(
            horizontal=config.DATA_ALIGNMENT_RIGHT['horizontal'],
            vertical=config.DATA_ALIGNMENT_RIGHT['vertical']
        )
        
        # Стиль границ для заголовков
        header_border_side = Side(
            border_style=config.HEADER_BORDER_STYLE['border_style'],
            color=config.HEADER_BORDER_STYLE['color']
        )
        header_border = Border(left=header_border_side, right=header_border_side, top=header_border_side, bottom=header_border_side)
        
        # Применяем форматирование к заголовкам таблицы
        for col_num, column in enumerate(df.columns, 1):
            cell = ws.cell(row=header_row, column=col_num)
            cell.font = header_font
            cell.alignment = header_alignment
            cell.fill = header_fill
            cell.border = header_border
            
            # Устанавливаем ширину колонки
            column_letter = cell.column_letter
            if column in config.WIDE_COLUMNS:
                ws.column_dimensions[column_letter].width = config.WIDE_COLUMNS[column]
            else:
                ws.column_dimensions[column_letter].width = config.DEFAULT_COLUMN_WIDTH
        
        # Применяем форматирование к данным (без границ)
        for row_num in range(config.EXCEL_DATA_START_ROW_NUM, len(df) + config.EXCEL_DATA_START_ROW_NUM):
            for col_num in range(1, len(df.columns) + 1):
                cell = ws.cell(row=row_num, column=col_num)
                cell.font = data_font
                
                # Получаем имя колонки
                column_name = df.columns[col_num - 1]
                
                # Применяем выравнивание в зависимости от колонки
                if column_name in config.RIGHT_ALIGNED_COLUMNS:
                    cell.alignment = data_alignment_right
                else:
                    cell.alignment = data_alignment
                
                # Применяем числовые форматы
                if column_name in config.PRICE_FORMAT_COLUMNS:
                    cell.number_format = config.PRICE_NUMBER_FORMAT
                elif column_name in config.ROI_FORMAT_COLUMNS:
                    cell.number_format = config.ROI_NUMBER_FORMAT
                elif column_name in config.EAN_FORMAT_COLUMNS:
                    cell.number_format = config.EAN_NUMBER_FORMAT
                
                # Добавляем формулу для колонки Price PL
                if column_name == 'Price PL':
                    # Находим колонку Price
                    price_col_num = None
                    for i, col in enumerate(df.columns):
                        if col == 'Price':
                            price_col_num = i + 1
                            break
                    
                    if price_col_num:
                        # Получаем буквы колонок
                        from openpyxl.utils import get_column_letter
                        price_col_letter = get_column_letter(price_col_num)
                        
                        # Создаем формулу: Price * G1 (курс обмена)
                        formula = f"={price_col_letter}{row_num}*$G$1"
                        cell.value = formula
                        
                        # Применяем формат числа (будет применен позже через config.PRICE_NUMBER_FORMAT)
                
                # Добавляем формулу для колонки Profit
                elif column_name == 'Profit':
                    # Находим нужные колонки
                    price_pl_col_num = None
                    cena_min_col_num = None
                    
                    for i, col in enumerate(df.columns):
                        if col == 'Price PL':
                            price_pl_col_num = i + 1
                        elif col == 'Cena min.':
                            cena_min_col_num = i + 1
                    
                    if price_pl_col_num and cena_min_col_num:
                        # Получаем буквы колонок
                        from openpyxl.utils import get_column_letter
                        price_pl_col_letter = get_column_letter(price_pl_col_num)
                        cena_min_col_letter = get_column_letter(cena_min_col_num)
                        
                        # Создаем формулу для расчета прибыли:
                        # Profit = (Cena min. / 1.23) - ((Cena min. * M1%) / 1.23) - Price PL - Доставка(G2) - Стоимость Prep Center(G3)
                        formula = f"=({cena_min_col_letter}{row_num}/1.23)-(({cena_min_col_letter}{row_num}*$M$1/100)/1.23)-{price_pl_col_letter}{row_num}-$G$2-$G$3"
                        cell.value = formula
                        
                        # Применяем формат числа (будет применен позже через config.PRICE_NUMBER_FORMAT)
                
                # Добавляем формулу для колонки ROI
                elif column_name == 'ROI':
                    # Находим нужные колонки
                    profit_col_num = None
                    cena_min_col_num = None
                    
                    for i, col in enumerate(df.columns):
                        if col == 'Profit':
                            profit_col_num = i + 1
                        elif col == 'Cena min.':
                            cena_min_col_num = i + 1
                    
                    if profit_col_num and cena_min_col_num:
                        # Получаем буквы колонок
                        from openpyxl.utils import get_column_letter
                        profit_col_letter = get_column_letter(profit_col_num)
                        cena_min_col_letter = get_column_letter(cena_min_col_num)
                        
                        # Создаем формулу для расчета ROI: (Profit / Cena min.)
                        # Формат 0% в config.ROI_NUMBER_FORMAT автоматически умножит на 100
                        formula = f"=IF({cena_min_col_letter}{row_num}<>0,{profit_col_letter}{row_num}/{cena_min_col_letter}{row_num},0)"
                        cell.value = formula
                        
                        # Применяем формат числа (будет применен позже через config.ROI_NUMBER_FORMAT)
                
                # Особое форматирование для гиперссылок
                elif column_name == 'Link' and pd.notna(df.iloc[row_num - config.EXCEL_DATA_START_ROW_NUM, col_num - 1]):
                    link_value = df.iloc[row_num - config.EXCEL_DATA_START_ROW_NUM, col_num - 1]
                    if str(link_value).startswith('http'):
                        # Создаем гиперссылку с текстом "Link"
                        cell.hyperlink = str(link_value)
                        cell.value = "Link"  # Отображаем текст "Link" вместо полной ссылки
                        cell.font = Font(name='Arial', size=10, color='0000FF', underline='single')
                        cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # Особое форматирование для Product Link гиперссылок
                elif column_name == 'Product Link' and pd.notna(df.iloc[row_num - config.EXCEL_DATA_START_ROW_NUM, col_num - 1]):
                    product_link_value = df.iloc[row_num - config.EXCEL_DATA_START_ROW_NUM, col_num - 1]
                    if str(product_link_value).startswith('http'):
                        # Создаем обычную гиперссылку через openpyxl (более надежно чем формула)
                        ean_value = df.iloc[row_num - config.EXCEL_DATA_START_ROW_NUM, df.columns.get_loc('EAN')] if 'EAN' in df.columns else ''
                        formatted_ean = format_ean_to_13_digits(ean_value) if ean_value else ''
                        
                        if formatted_ean:
                            # Создаем URL и присваиваем как гиперссылку
                            product_url = f"https://api.qogita.com/variants/link/{formatted_ean}/"
                            cell.hyperlink = product_url
                            cell.value = "View Product"  # Отображаемый текст
                            cell.font = Font(name='Arial', size=10, color='0000FF', underline='single')
                            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Добавляем "Date:" в ячейку A1
        date_label_cell = ws['A1']
        date_label_cell.value = "Date:"
        date_label_cell.font = Font(
            name=config.TITLE_FONT_SETTINGS['name'],
            size=config.TITLE_FONT_SETTINGS['size'],
            bold=config.TITLE_FONT_SETTINGS['bold']
        )
        
        # Добавляем дату в ячейку B1
        date_cell = ws['B1']
        date_cell.value = datetime.now().strftime('%d.%m.%Y')
        date_cell.font = Font(
            name=config.TITLE_FONT_SETTINGS['name'],
            size=config.TITLE_FONT_SETTINGS['size'],
            bold=config.TITLE_FONT_SETTINGS['bold']
        )
        
        # Добавляем гиперссылку Help в ячейку A3
        help_cell = ws['A3']
        help_cell.value = "Help"
        help_cell.hyperlink = "https://t.me/iilluummiinnaattoorr"
        help_cell.font = Font(
            name=config.TITLE_FONT_SETTINGS['name'],
            size=config.TITLE_FONT_SETTINGS['size'],
            bold=config.TITLE_FONT_SETTINGS['bold'],
            color='0000FF',  # Синий цвет для гиперссылки
            underline='single'
        )
        
        # Активируем фильтр на строке заголовков (4-я строка)
        header_row = config.EXCEL_HEADER_ROW_NUM
        last_column = len(df.columns)
        last_data_row = len(df) + config.EXCEL_DATA_START_ROW_NUM - 1
        
        # Определяем диапазон для фильтра (от заголовков до последней строки данных)
        filter_range = f"A{header_row}:{chr(65 + last_column - 1)}{last_data_row}"
        ws.auto_filter.ref = filter_range
        
        # Закрепляем области до 4-й строки включительно
        ws.freeze_panes = f"A{config.EXCEL_DATA_START_ROW_NUM}"  # Закрепляем до 5-й строки (после заголовков)
        
        # Применяем условное форматирование
        for column_name, format_config in config.CONDITIONAL_FORMAT_COLUMNS.items():
            if column_name in df.columns:
                # Находим номер колонки
                col_index = df.columns.get_loc(column_name) + 1
                col_letter = get_column_letter(col_index)
                
                # Определяем диапазон данных для условного форматирования
                start_row = config.EXCEL_DATA_START_ROW_NUM
                end_row = len(df) + config.EXCEL_DATA_START_ROW_NUM - 1
                range_string = f"{col_letter}{start_row}:{col_letter}{end_row}"
                
                # Создаем правило цветовой шкалы
                rule = ColorScaleRule(
                    start_type='num',
                    start_value=format_config['start_value'],
                    start_color=format_config['start_color'],
                    mid_type='num',
                    mid_value=format_config['mid_value'],
                    mid_color=format_config['mid_color'],
                    end_type='num',
                    end_value=format_config['end_value'],
                    end_color=format_config['end_color']
                )
                
                # Применяем правило к диапазону
                ws.conditional_formatting.add(range_string, rule)
                print(f"Применено условное форматирование для колонки '{column_name}' в диапазоне {range_string}")
        
        # Сохраняем файл
        wb.save(output_file)
        print(f"Файл сохранен с форматированием: {output_file}")
        
    except Exception as e:
        print(f"Ошибка при форматировании файла {output_file}: {str(e)}")
        # Если форматирование не удалось, сохраняем без форматирования
        df.to_excel(output_file, index=False)
        print(f"Файл сохранен без форматирования: {output_file}")

def add_price_pl_column(df):
    """
    Добавляет колонку 'Price PL' для расчета цены по курсу валют
    """
    # Добавляем колонку Price PL с пустыми значениями
    # Формула будет добавлена позже при форматировании Excel
    df['Price PL'] = None
    
    print("Добавлена колонка 'Price PL' для расчета цены по курсу валют")
    return df

def add_roi_column(df):
    """
    Добавляет колонку 'ROI' для расчета возврата инвестиций
    """
    # Добавляем колонку ROI с пустыми значениями
    # Формула будет добавлена позже при форматировании Excel
    df['ROI'] = None
    
    print("Добавлена колонка 'ROI' для расчета возврата инвестиций")
    return df

def merge_excel_files_from_list(file_paths, original_filename=None):
    """
    Объединяет файлы Excel по EAN коду из списка файлов.
    Предназначено для работы с загруженными в бот файлами
    
    Args:
        file_paths: список путей к файлам для обработки
        original_filename: оригинальное имя файла поставщика (для создания итогового файла)
    
    Returns:
        dict: статистика обработки
    """
    
    # Разделяем файлы на TradeWatch и остальные
    tradewatch_files = []
    other_files = []
    
    for file_path in file_paths:
        filename = os.path.basename(file_path)
        if filename.startswith('TradeWatch') and filename.endswith('.xlsx'):
            tradewatch_files.append(file_path)
        elif filename.endswith('.xlsx') and not any(filename.startswith(prefix) for prefix in config.EXCLUDED_FILE_PREFIXES):
            other_files.append(file_path)
    
    if not tradewatch_files:
        print("Не найдены файлы TradeWatch среди загруженных файлов")
        return None
    
    print(f"Найдено файлов TradeWatch: {len(tradewatch_files)}")
    for file in tradewatch_files:
        print(f"  - {os.path.basename(file)}")
    
    # Собираем все EAN коды из файлов TradeWatch
    all_ean_data = []
    
    for file_path in tradewatch_files:
        try:
            print(f"\nОбрабатываем файл: {os.path.basename(file_path)}")
            df = pd.read_excel(file_path, sheet_name=config.TRADEWATCH_SHEET_NAME)
            df['source_file'] = os.path.basename(file_path)
            
            # Форматируем EAN в 13-цифровом формате
            df['EAN'] = df['EAN'].apply(format_ean_to_13_digits)
            
            all_ean_data.append(df)
            print(f"  Найдено EAN кодов: {len(df)}")
        except Exception as e:
            print(f"Ошибка при чтении файла {file_path}: {str(e)}")
    
    if not all_ean_data:
        print("Не удалось загрузить данные из файлов TradeWatch")
        return None
    
    # Объединяем все данные TradeWatch
    combined_tradewatch = pd.concat(all_ean_data, ignore_index=True)
    print(f"\nВсего уникальных EAN кодов из TradeWatch: {combined_tradewatch['EAN'].nunique()}")
    
    if not other_files:
        print("Не найдены другие Excel файлы для объединения")
        # Рассчитываем прибыль и ROI для данных TradeWatch
        combined_tradewatch = calculate_profit_and_roi(combined_tradewatch)
        
        # Добавляем колонку Price PL
        combined_tradewatch = add_price_pl_column(combined_tradewatch)
        
        # Создаем гиперссылки
        combined_tradewatch = create_hyperlinks(combined_tradewatch)
        
        # Создаем Product Link гиперссылки
        combined_tradewatch = create_product_links(combined_tradewatch)
        
        # Определяем выходной файл в той же папке, что и первый TradeWatch файл
        output_dir = os.path.dirname(tradewatch_files[0])
        output_file = os.path.join(output_dir, config.OUTPUT_FILE_MERGED_TRADEWATCH)
        save_formatted_excel(combined_tradewatch, output_file)
        
        stats = {
            'total_rows': len(combined_tradewatch),
            'unique_ean': combined_tradewatch['EAN'].nunique() if 'EAN' in combined_tradewatch.columns else 0,
            'files_processed': 0,  # только TradeWatch файлы
            'output_file': output_file
        }
        
        print(f"Сохранены данные TradeWatch в файл: {output_file}")
        return stats
    
    print(f"\nНайдено других Excel файлов: {len(other_files)}")
    for file in other_files:
        print(f"  - {os.path.basename(file)}")
    
    # Объединяем с другими файлами
    merged_results = []
    
    for other_file in other_files:
        try:
            print(f"\nОбъединяем с файлом: {os.path.basename(other_file)}")
            
            # Читаем файл
            other_df = pd.read_excel(other_file)
            
            # Ищем колонку с GTIN
            gtin_column = None
            for col in config.POSSIBLE_GTIN_COLUMNS:
                if col in other_df.columns:
                    gtin_column = col
                    break
            
            if gtin_column is None:
                print(f"  В файле {other_file} не найдена колонка GTIN")
                continue
            
            # Форматируем GTIN в 13-цифровой формат
            other_df_clean = other_df[other_df[gtin_column].notna()].copy()
            other_df_clean[gtin_column] = other_df_clean[gtin_column].apply(format_ean_to_13_digits)
            other_df_clean = other_df_clean[other_df_clean[gtin_column].notna()].copy()
            
            # Объединяем по EAN
            merged = pd.merge(combined_tradewatch, other_df_clean, left_on='EAN', right_on=gtin_column, how='inner')
            
            if not merged.empty:
                merged['merged_with'] = os.path.basename(other_file)
                merged_results.append(merged)
                print(f"  Найдено совпадений: {len(merged)}")
            else:
                print(f"  Совпадений не найдено")
                
        except Exception as e:
            print(f"Ошибка при объединении с файлом {other_file}: {str(e)}")
    
    # Сохраняем результаты
    if merged_results:
        # Объединяем все результаты
        final_result = pd.concat(merged_results, ignore_index=True)
        
        # Рассчитываем прибыль и ROI
        final_result = calculate_profit_and_roi(final_result)
        
        # Добавляем колонку Price PL
        final_result = add_price_pl_column(final_result)
        
        # Создаем гиперссылки
        final_result = create_hyperlinks(final_result)
        
        # Создаем Product Link гиперссылки
        final_result = create_product_links(final_result)
        
        # Упорядочиваем колонки в нужном порядке и оставляем только нужные
        available_ordered_columns = [col for col in config.DESIRED_COLUMN_ORDER if col in final_result.columns]
        final_column_order = available_ordered_columns
        final_result = final_result[final_column_order]
        
        # Определяем выходной файл в той же папке, что и первый TradeWatch файл
        output_dir = os.path.dirname(tradewatch_files[0])
        
        # Создаем имя файла на основе оригинального имени с timestamp
        if original_filename:
            # Убираем расширение и добавляем timestamp
            base_name = os.path.splitext(os.path.basename(original_filename))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{base_name}_result_{timestamp}.xlsx"
        else:
            # Используем стандартное имя, если оригинальное имя не предоставлено
            output_filename = config.OUTPUT_FILE_WITH_CALCULATIONS
        
        output_file = os.path.join(output_dir, output_filename)
        save_formatted_excel(final_result, output_file)
        
        # Подготавливаем статистику
        stats = {
            'total_rows': len(final_result),
            'unique_ean': final_result['EAN'].nunique() if 'EAN' in final_result.columns else 0,
            'files_processed': len(other_files),
            'output_file': output_file
        }
        
        print(f"\nРезультат сохранен в файл: {output_file}")
        print(f"Всего строк в результате: {stats['total_rows']}")
        print(f"Уникальных EAN кодов: {stats['unique_ean']}")
        print(f"Порядок колонок: {final_column_order}")
        
        return stats
    else:
        print("\nСовпадений не найдено, сохраняем только данные TradeWatch")
        # Рассчитываем прибыль и ROI для данных TradeWatch
        combined_tradewatch = calculate_profit_and_roi(combined_tradewatch)
        
        # Добавляем колонку Price PL
        combined_tradewatch = add_price_pl_column(combined_tradewatch)
        
        # Создаем гиперссылки
        combined_tradewatch = create_hyperlinks(combined_tradewatch)
        
        # Создаем Product Link гиперссылки
        combined_tradewatch = create_product_links(combined_tradewatch)
        
        # Определяем выходной файл в той же папке, что и первый TradeWatch файл
        output_dir = os.path.dirname(tradewatch_files[0])
        output_file = os.path.join(output_dir, config.OUTPUT_FILE_TRADEWATCH_ONLY)
        save_formatted_excel(combined_tradewatch, output_file)
        
        stats = {
            'total_rows': len(combined_tradewatch),
            'unique_ean': combined_tradewatch['EAN'].nunique() if 'EAN' in combined_tradewatch.columns else 0,
            'files_processed': 0,
            'output_file': output_file
        }
        
        print(f"Сохранены данные TradeWatch в файл: {output_file}")
        return stats

def process_supplier_with_tradewatch_auto(supplier_file_path, temp_dir, progress_callback=None):
    """
    Новая функция для автоматической обработки файла поставщика с TradeWatch
    
    Args:
        supplier_file_path: путь к файлу поставщика
        temp_dir: временная папка для скачивания файлов
        progress_callback: функция для отслеживания прогресса (опционально)
    
    Returns:
        dict: статистика обработки и путь к результату
    """
    try:
        print(f"Начинаем обработку файла поставщика: {supplier_file_path}")
        
        # Создаем временную папку для скачивания
        download_dir = os.path.join(temp_dir, "tradewatch_downloads")
        os.makedirs(download_dir, exist_ok=True)
        
        # Обрабатываем файл поставщика и получаем файлы TradeWatch
        print("Извлекаем EAN коды и обрабатываем через TradeWatch...")
        tradewatch_files = process_supplier_file_with_tradewatch(supplier_file_path, download_dir, progress_callback=progress_callback)
        
        if not tradewatch_files:
            return {
                'success': False,
                'error': 'Не удалось получить данные из TradeWatch',
                'files_processed': 0
            }
        
        print(f"Получено {len(tradewatch_files)} файлов TradeWatch")
        
        # Проверяем, что все файлы существуют
        print("Проверка файлов TradeWatch:")
        for file_path in tradewatch_files:
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"  ✅ {file_path} (размер: {size} байт)")
            else:
                print(f"  ❌ {file_path} - НЕ НАЙДЕН!")
        
        # Объединяем файлы поставщика с файлами TradeWatch
        print("Объединяем файлы...")
        
        # Создаем список всех файлов для объединения
        all_files = [supplier_file_path] + tradewatch_files
        result = merge_excel_files_from_list(all_files, supplier_file_path)
        
        if result:
            print(f"Обработка завершена успешно!")
            print(f"Результат сохранен в: {result['output_file']}")
            
            # НЕ удаляем временные файлы TradeWatch сразу - они понадобятся для отладки
            # Очистка происходит в telegram_bot.py после отправки результата
            
            return {
                'success': True,
                'output_file': result['output_file'],
                'total_rows': result['total_rows'],
                'unique_ean': result['unique_ean'],
                'files_processed': len(tradewatch_files),
                'supplier_file': supplier_file_path,
                'tradewatch_files_count': len(tradewatch_files)
            }
        else:
            return {
                'success': False,
                'error': 'Ошибка при объединении файлов',
                'files_processed': len(tradewatch_files)
            }
            
    except Exception as e:
        print(f"Ошибка при обработке: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'files_processed': 0
        }

def main():
    """Основная функция для запуска скрипта с расчетами"""
    current_directory = os.getcwd()
    print(f"Рабочая директория: {current_directory}")
    print("=" * 50)
    
    merge_excel_files_by_ean_with_calculations(current_directory)

if __name__ == "__main__":
    main()


def process_supplier_with_tradewatch_interruptible(supplier_file_path, temp_dir, stop_flag_callback=None, progress_callback=None):
    """
    Функция для обработки файла поставщика с возможностью остановки процесса
    
    Args:
        supplier_file_path: путь к файлу поставщика
        temp_dir: временная папка для скачивания файлов
        stop_flag_callback: функция для проверки флага остановки
        progress_callback: функция для обновления прогресса
    
    Returns:
        dict: статистика обработки и путь к результату
    """
    try:
        print(f"Начинаем обработку файла поставщика: {supplier_file_path}")
        
        # Создаем временную папку для скачивания
        download_dir = os.path.join(temp_dir, "tradewatch_downloads")
        os.makedirs(download_dir, exist_ok=True)
        
        # Импортируем функцию с поддержкой остановки
        from tradewatch_login import process_supplier_file_with_tradewatch_interruptible
        
        # Обрабатываем файл поставщика и получаем файлы TradeWatch
        if progress_callback:
            progress_callback("🔄 Извлекаю EAN коды и обрабатываю через TradeWatch...")
        
        print("Извлекаем EAN коды и обрабатываем через TradeWatch...")
        tradewatch_files = process_supplier_file_with_tradewatch_interruptible(
            supplier_file_path, 
            download_dir, 
            stop_flag_callback=stop_flag_callback,
            progress_callback=progress_callback
        )
        
        if not tradewatch_files:
            return {
                'success': False,
                'error': 'Не удалось получить данные из TradeWatch',
                'files_processed': 0
            }
        
        # Проверяем флаг остановки перед объединением
        if stop_flag_callback and stop_flag_callback():
            print("🛑 Процесс остановлен перед объединением файлов")
        
        print(f"Получено {len(tradewatch_files)} файлов TradeWatch")
        
        # Проверяем, что все файлы существуют
        print("Проверка файлов TradeWatch:")
        for file_path in tradewatch_files:
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"  ✅ {file_path} (размер: {size} байт)")
            else:
                print(f"  ❌ {file_path} - НЕ НАЙДЕН!")
        
        # Объединяем файлы поставщика с файлами TradeWatch
        if progress_callback:
            progress_callback("📊 Объединяю файлы и создаю отчёт...")
        
        print("Объединяем файлы...")
        
        # Создаем список всех файлов для объединения
        all_files = [supplier_file_path] + tradewatch_files
        result = merge_excel_files_from_list(all_files, supplier_file_path)
        
        if result:
            status_msg = "🛑 Частичный отчёт создан!" if (stop_flag_callback and stop_flag_callback()) else "✅ Обработка завершена успешно!"
            print(status_msg)
            print(f"Результат сохранен в: {result['output_file']}")
            
            return {
                'success': True,
                'output_file': result['output_file'],
                'total_rows': result['total_rows'],
                'unique_ean': result['unique_ean'],
                'files_processed': len(tradewatch_files),
                'supplier_file': supplier_file_path,
                'tradewatch_files_count': len(tradewatch_files),
                'is_partial': stop_flag_callback and stop_flag_callback() if stop_flag_callback else False
            }
        else:
            return {
                'success': False,
                'error': 'Ошибка при объединении файлов',
                'files_processed': len(tradewatch_files)
            }
            
    except Exception as e:
        print(f"Ошибка при обработке: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'files_processed': 0
        }
