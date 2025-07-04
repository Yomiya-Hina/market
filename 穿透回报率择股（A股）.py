# -*- coding: utf-8 -*-
import re
import akshare as ak
import pandas as pd
pd.set_option('display.max_columns', None)  # 显示所有列
pd.set_option('display.max_rows', None)
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt


# ======================
# 1. 基本面筛选模块
# ======================
def fundamental_screening():
    hs300 = ak.stock_history_dividend()
    # 先转换为数值类型
    hs300["分红次数"] = pd.to_numeric(hs300["分红次数"], errors='coerce')
    hs300["年均股息"] = pd.to_numeric(hs300["年均股息"], errors='coerce')
    a600 = hs300[(hs300["分红次数"]  > 2) & (hs300["年均股息"] <= 20) & (hs300["年均股息"] > 3.4)]
    hs600 = a600['代码'].tolist()
    total_count = len(hs600)
    print(f"总记录数: {total_count} 条")
    # 获取最新财务数据
    qualified_stocks = []
    for stock in hs600:  # 示例取前100支（实际可全量）
        sto = _executor(stock)
        if sto:
            qualified_stocks.append(sto)
    return qualified_stocks


def chinese_number_to_float(text):
    """
    增强版中文数字转换函数，处理所有异常情况：
    - 处理中文单位（亿/万）
    - 处理布尔值字符串（False/True）
    - 处理空值/NaN
    - 处理普通数字字符串
    """
    # 处理空值和NaN
    if pd.isna(text) or text is None:
        return 0.0  # 或者 return float('nan')

    text = str(text).strip()

    # 处理布尔值字符串
    if text.lower() in ('false', 'true'):
        return 0.0

    # 移除可能存在的千分位逗号
    text = text.replace(',', '')

    # 处理中文单位
    try:
        if '亿' in text:
            return float(text.replace('亿', '')) * 1e8
        elif '万' in text:
            return float(text.replace('万', '')) * 1e4
        else:
            return float(text)
    except ValueError:
        return 0.0

def _executor(stock):
    print(stock)
    current_year = pd.Timestamp.now().year
    try:
        b = ak.stock_fhps_detail_em(stock).sort_values("报告期", ascending=False)
    except TypeError:
        print("return 该股无数据")
        return
    # 首先确保'公告日期'列是datetime类型
    b['报告期'] = pd.to_datetime(b['报告期'])
    # 应用调整函数
    # b['报告期'] = b['报告期'].apply(adjust_announcement_date)

    # 如果需要将日期格式转换回字符串（可选）
    b['报告期'] = b['报告期'].dt.strftime('%Y-%m-%d')
    # 确保是datetime类型
    b["报告期"] = pd.to_datetime(b["报告期"])
    target_years = [current_year - 1, current_year - 2, current_year - 3, current_year - 4, current_year - 5]
    target_years_df = b[b["报告期"].dt.year.isin(target_years)]
    # 创建原始DataFrame的独立副本
    df_clean = target_years_df.copy()
    # 在副本上操作
    df_clean['年份'] = pd.to_datetime(df_clean['报告期']).dt.year
    annual_dividends = df_clean.groupby('年份')['现金分红-现金分红比例'].sum().reset_index()
    dividend_rate = df_clean.groupby('年份')['现金分红-股息率'].sum().reset_index()
    if annual_dividends.empty:
        print("return empty")
        return
    new_dividends = annual_dividends.iloc[-1]["现金分红-现金分红比例"]/10

    average_total = annual_dividends['现金分红-现金分红比例'].mean()/10
    avg_dividend_rate = dividend_rate['现金分红-股息率'].mean()
    dhk_spot_em_df = ak.stock_zh_a_hist(symbol=stock).iloc[-1]

    # 股息率大于5%，最新派息大于等于最近5年平均派息的0.6
    if new_dividends / dhk_spot_em_df['收盘'] > 0.046 and new_dividends / average_total >= 0.6 and avg_dividend_rate > 0.05:
        print("return gx")
    else:
        print("return0")
        return

    df_fin = ak.stock_financial_debt_ths(stock, "按年度").iloc[0]
    if df_fin["报告期"] < current_year - 1:
        print("return 已退市")
        return
    if '货币资金' in df_fin.to_frame().T.columns and not pd.isna(df_fin['货币资金']):
        try:
            yszk = chinese_number_to_float(df_fin['应收票据及应收账款']) if not pd.isna(df_fin['应收票据及应收账款']) else 0
        except KeyError:
            if '应收账款' in df_fin.to_frame().T.columns:
                yszk = chinese_number_to_float(df_fin['应收账款']) if not pd.isna(df_fin['应收账款']) else 0
            else:
                yszk = 0
        xj = chinese_number_to_float(df_fin['货币资金'])
        try:
            dqdk = chinese_number_to_float(df_fin['短期借款']) if not pd.isna(df_fin['短期借款']) and df_fin['短期借款'] is not False else 1
        except KeyError:
            dqdk = 1
        # ldfz = df_fin[df_fin['STD_ITEM_NAME'] == '流动负债合计'].iloc[0]["AMOUNT"]
        # 过滤现金及等价物小于等于2倍应收帐款 或 现金及等价物 / 短期贷款小于50%
        if xj <= yszk * 2 or xj / dqdk < 0.5:
            print("return1")
            return
    df_fin12 = ak.stock_financial_report_sina(stock,'现金流量表')
    # 获取当前日期，并构造去年12月31日
    last_year_end = datetime.now().replace(year=datetime.now().year - 1, month=12, day=31)
    # 格式化为YYYYMMDD（如20241231）
    formatted_date = last_year_end.strftime("%Y%m%d")
    try:
        df_fin12_new_df = df_fin12[df_fin12["报告日"] == formatted_date].iloc[0]
    except IndexError:
        print("return1.5")
        return
    jyxj = df_fin12_new_df["经营活动产生的现金流量净额"]
    tzxj = df_fin12_new_df["投资活动产生的现金流量净额"]
    rzxj = df_fin12_new_df["筹资活动产生的现金流量净额"]
    # 融资业务现金净额 < 0 and  融资业务现金净额的绝对值 / 经营业务现金净额大于30% and 投资业务现金净额的绝对值 / 经营业务现金净额小于70%
    if rzxj < 0 and abs(rzxj) / jyxj > 0.3 and abs(tzxj) / jyxj < 0.7:
        pass
    else:
        print("return2")
        return
    df_fin2 = ak.stock_financial_abstract_ths(stock).iloc[-1]
    zcfzl = df_fin2["资产负债率"]
    avg_roe = df_fin2["净资产收益率-摊薄"]
    zcfzl_decimal = float(zcfzl.strip("%"))
    avg_roe_decimal = float(avg_roe.strip("%"))
    # 核心筛选条件
    if avg_roe_decimal > 0  and zcfzl_decimal < 54:
        pass
    else:
        print("return3")
        return
    print("return su")
    return stock

# 创建一个函数来调整日期
def adjust_announcement_date(date):
    print(date.month)
    if pd.isna(date):
        return date
    if date.month in [1, 2, 3, 4]:  # 一季度
        return datetime(date.year - 1, 12, 31)  # 改为去年的最后一天
    return date

# ======================
# 4. 主执行模块
# ======================
def main():
    # 步骤1：基本面初筛
    print("=" * 50)
    print("开始基本面筛选...")
    fundamental_picks = fundamental_screening()

    print(fundamental_picks)
    print(f"基本面达标股票: {len(fundamental_picks)}支")

    #步骤4：获取实时数据
    if fundamental_picks:
        print("\n最终选股结果:")
        realtime_data = ak.stock_zh_a_spot_em()
        result_df = realtime_data[realtime_data['代码'].isin(fundamental_picks)][
            ['代码', '名称', '最新价', '涨跌幅', '换手率', '量比', '成交额', '市盈率-动态', '市净率']
        ]
        print(result_df)

        # 可视化展示
        plt.figure(figsize=(12, 6))
        result_df.set_index('名称')['涨跌幅'].plot(kind='bar', color=np.where(result_df['涨跌幅'] > 0, 'r', 'g'))
        plt.title('精选股票涨跌幅分布')
        plt.ylabel('涨跌幅(%)')
        plt.axhline(0, color='black', linestyle='--')
        plt.tight_layout()
        # 如果还是乱码，可以尝试加上以下两行
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False
        plt.show()
    else:
        print("今日无符合条件股票")

if __name__ == "__main__":

    # a = ak.stock_financial_hk_report_em('00700',indicator='报告期')
    # print(a[a['REPORT_DATE'] == '2025-03-31 00:00:00'])
    # print(a[a['STD_ITEM_NAME'] == '短期贷款'])
    # print(a[a['STD_ITEM_NAME'] == '流动负债合计'])
    # print(a[a['STD_ITEM_NAME'] == '融资业务现金净额'])

    # _executor('000022')
    main()
    # hs300 = ak.stock_zh_a_spot_em()['代码'].tolist()
    # print(hs300)


    # hs300 = ak.stock_history_dividend()['代码'].tolist()
    # print(ak.stock_zh_a_spot_em().iloc[0])
    # print(len(hs300))

