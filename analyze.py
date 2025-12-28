import re
import json
import os
from collections import defaultdict, deque

import tqdm
import glob


STAT_DIR = ""
DATA_FILE = os.path.join(STAT_DIR, "data.json")


강화비용 = [0,10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 40000, 50000, 70000, 100000, 150000, 200000]

def parse_chat_logs(files):
    """
    Parses chat logs into message blocks.
    A block starts with [Name] [Time] or [Name].
    """
    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            current_name = None
            current_lines = []
            
            for line in f:
                match_time = re.match(r'^\[(.*?)\] \[(.*?)\] (.*)', line)
                if match_time:
                    if current_name:
                        yield current_name, "\n".join(current_lines)
                    current_name = match_time.group(1)
                    current_lines = [match_time.group(3)]
                    continue
                

                match_no_time = re.match(r'^\[(.*?)\] (.*)', line)
                if match_no_time:
                    if current_name:
                        yield current_name, "\n".join(current_lines)
                    current_name = match_no_time.group(1)
                    current_lines = [match_no_time.group(2)]
                    continue
                
                # Continuation line
                if current_name:
                    current_lines.append(line.strip())
            
            # Yield last message
            if current_name:
                yield current_name, "\n".join(current_lines)

def analyze():
    txt_files = glob.glob(os.path.join(STAT_DIR, "*.txt"))
    if not txt_files:
        print(f"No .txt files found in {STAT_DIR}")
        return

    print(f"Analyzing {len(txt_files)} files: {[os.path.basename(f) for f in txt_files]}")


    users = defaultdict(lambda: 0)
    

    stats = defaultdict(lambda: {
        "attempts": 0, "success": 0, "maintain": 0, "fail": 0, "destroy": 0,
        "total_cost": 0, "sell_count": 0, "sell_total": 0
    })


    SPLIT_PATTERN = r'\n\[.*?\] \[.*?\]'

    full_text = ""
    for f_path in txt_files:
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                full_text += "\n" + f.read()
        except Exception as e:
            print(f"Error reading {f_path}: {e}")
            continue


    parts = re.split(r'\n\[(.*?)\] \[(.*?)\]', full_text)
    
    i = 1
    while i < len(parts) - 2:
        chat = parts[i+2]
        i += 3
        
        chat = chat.strip()
        if not chat: continue
        
        # 1. Success
        if "강화 성공" in chat:
            used_gold_match = re.search(r'사용 골드: -([\d,]+)G', chat)
            gold_match = re.search(r'남은 골드: ([\d,]+)G', chat)
            sword_match = re.search(r'획득 검: \[(\+\d+)\] (.+)', chat)

            if not sword_match:
                continue
                
            used_gold = used_gold_match.group(1) if used_gold_match else None
            gold = gold_match.group(1) if gold_match else None
            level = sword_match.group(1)
            sword_name = sword_match.group(2)
            
            if sword_name:
                sword_name = sword_name.replace("』", "")
            
            if used_gold:
                used_gold = int(used_gold.replace(",", ""))
            else:
                used_gold = 0
                
            if gold:
                gold = int(gold.replace(",", ""))
            else:
                gold = 0
            
            if not level:
                continue
                
            src_level = int(level.replace("+", ""))

            stats[src_level-1]['attempts'] += 1
            stats[src_level-1]['success'] += 1
            stats[src_level-1]['total_cost'] += 강화비용[src_level-1]
            
        # 2. Idle (Maintain)
        if "강화 유지" in chat:
            used_gold_match = re.search(r'사용 골드: -([\d,]+)G', chat)
            gold_match = re.search(r'남은 골드: ([\d,]+)G', chat)
            sword_match = re.search(r'\[(\+\d+)\] (.+)의 레벨이 유지되었습니다.', chat)

            if not sword_match:
                continue

            used_gold = used_gold_match.group(1) if used_gold_match else None
            gold = gold_match.group(1) if gold_match else None
            level = sword_match.group(1)  
            sword_name = sword_match.group(2) 

            if sword_name:
                sword_name = sword_name.replace("』", "")

            if used_gold:
                used_gold = int(used_gold.replace(",", ""))
            else:
                used_gold = 0
                
            if gold:
                gold = int(gold.replace(",", ""))
            else:
                gold = 0
    
            if not level:
                continue
                
            src_level = int(level.replace("+", ""))

            stats[src_level]['attempts'] += 1
            stats[src_level]['maintain'] += 1
            stats[src_level]['total_cost'] += 강화비용[src_level]

        # 3.1 Destruction
        if "산산조각 나서" in chat:
            src_level_match = re.search(r'『\[\+(\d+)\]', chat)
            if src_level_match:
                src_level = int(src_level_match.group(1))
                stats[src_level]['attempts'] += 1
                stats[src_level]['destroy'] += 1
                stats[src_level]['total_cost'] += 강화비용[src_level]

        # 4. Sell
        if "검 판매" in chat:
            src_level_match = re.search(r"자네의 '\[\+(\d+)\]", chat)
            if src_level_match:
                src_level = int(src_level_match.group(1))

                # 💶획득 골드: +76,615G
                gain_gold_match = re.search(r'획득 골드: \+([\d,]+)G', chat)
                # 💰현재 보유 골드: 11,952,477G
                gold_match = re.search(r'현재 보유 골드: ([\d,]+)G', chat)
        
                gain_gold = gain_gold_match.group(1) if gain_gold_match else "0"
                gold = gold_match.group(1) if gold_match else "0"

                gain_gold = int(gain_gold.replace(",", ""))
                gold = int(gold.replace(",", ""))
        
                stats[src_level]['sell_count'] += 1
                stats[src_level]['sell_total'] += gain_gold


    sorted_levels = sorted(stats.keys())
    if not sorted_levels:
        return

    max_level = sorted_levels[-1]
    cost_to_reach = {0: 0} 
    
    # 누적 확률 계산을 위한 성공 확률 및 유지 확률 저장
    level_success_probs = {}
    level_maintain_probs = {}
    
    analysis_out = []

    for lvl in range(max_level + 1):
        if lvl not in stats:
            continue
            
        data = stats[lvl]
        total = data['attempts']
        if total == 0: continue
        
        s = data['success']
        m = data['maintain']
        d = data['destroy']
        
        p_s = s / total
        p_m = m / total
        p_d = d / total
        
        # 누적 확률 계산을 위해 성공 확률 및 유지 확률 저장
        level_success_probs[lvl] = p_s
        level_maintain_probs[lvl] = p_m
        
        avg_cost = data['total_cost'] / total
        
        avg_sell = 0

        if data['sell_count'] > 0:
            avg_sell = data['sell_total'] / data['sell_count']

            

        # Recursive Calculation
        prev_cum_cost = cost_to_reach.get(lvl, 0)
        
        # Cost to go L -> L+1
        if p_s > 0:
            step_cost = (avg_cost + p_d * prev_cum_cost) / p_s
        else:
            step_cost = 0 
            
        next_cum_cost = prev_cum_cost + step_cost
        cost_to_reach[lvl + 1] = next_cum_cost
        
        expected_profit = avg_sell - prev_cum_cost

        sim_costs = []
        sim_attempts = []

        if not hasattr(analyze, "level_probs"):
            analyze.level_probs = {}
        
        analyze.level_probs[lvl] = {
            's': p_s, 'm': p_m, 'd': p_d, 'cost': avg_cost, 'level_cost': 강화비용[lvl]
        }
        
        import random
        import math
        
        SIM_RUNS = 50000
        
        def simulate_run(target_lvl):
            curr_lvl = 0
            total_c = 0
            total_a = 0
            
            while curr_lvl < target_lvl:
                if curr_lvl not in analyze.level_probs:
                    return None, None 
                probs = analyze.level_probs[curr_lvl]
                
                cost = probs['level_cost'] 
                
                total_c += cost
                total_a += 1
                
                roll = random.random()
                if roll < probs['s']:
                    curr_lvl += 1
                elif roll < probs['s'] + probs['m']:
                    # Maintain
                    pass
                else:
                    # Destroy -> Reset to 0
                    curr_lvl = 0
            
            return total_c, total_a

        if lvl > 0:
            can_sim = True
            for l in range(lvl):
                if l not in analyze.level_probs:
                    can_sim = False
                    break
            
            if can_sim and analyze.level_probs[lvl-1]['s'] > 0:
                for _ in tqdm.tqdm(range(SIM_RUNS)):
                    sc, sa = simulate_run(lvl)
                    if sc is not None:
                        sim_costs.append(sc)
                        sim_attempts.append(sa)
            
            if sim_costs:
                mean_cost = sum(sim_costs) / len(sim_costs)
                variance_cost = sum((x - mean_cost) ** 2 for x in sim_costs) / len(sim_costs)
                std_dev_cost = math.sqrt(variance_cost)
                
                mean_attempts = sum(sim_attempts) / len(sim_attempts)
                
                time_efficiency = expected_profit / mean_attempts if mean_attempts > 0 else 0
            else:
                std_dev_cost = 0
                mean_attempts = 0
                time_efficiency = 0
        else:
            std_dev_cost = 0
            mean_attempts = 0
            time_efficiency = 0

        # 순수 성공 확률: 각 단계에서 성공 확률만 곱한 값 (유지, 파괴 무시, 한 번에 연속 성공 확률)
        pure_success_prob = 1.0
        for prev_lvl in range(lvl):
            if prev_lvl in level_success_probs:
                pure_success_prob *= level_success_probs[prev_lvl]
            else:
                pure_success_prob = 0.0
                break

        # 누적 확률: 유지를 고려한 실제 도달 확률
        # 유지가 발생해도 다시 시도할 수 있으므로, 각 단계에서 성공할 확률을 곱함
        # 각 단계에서 성공할 확률 = 성공 확률 / (1 - 유지 확률)
        # 이는 유지가 발생해도 다시 시도할 수 있으므로, 유지를 제외한 확률로 정규화
        cumulative_prob = 1.0
        for prev_lvl in range(lvl):
            if prev_lvl in level_success_probs:
                p_s_prev = level_success_probs[prev_lvl]
                p_m_prev = level_maintain_probs.get(prev_lvl, 0)
                # 유지를 고려한 실제 성공 확률
                # 유지가 발생해도 다시 시도할 수 있으므로, 유지를 제외한 확률로 정규화
                # 성공 확률 / (성공 확률 + 파괴 확률) = 성공 확률 / (1 - 유지 확률)
                if p_m_prev < 1.0:  # 유지 확률이 1이 아닌 경우만
                    adjusted_success_prob = p_s_prev / (1.0 - p_m_prev)
                else:
                    adjusted_success_prob = 0.0
                cumulative_prob *= adjusted_success_prob
            else:
                cumulative_prob = 0.0
                break

        row = {
            "level": lvl,
            "attempts": total,
            "success": s,
            "maintain": m,
            "destroy": d,
            "prob_success": round(p_s * 100, 2),
            "prob_maintain": round(p_m * 100, 2),
            "prob_destroy": round(p_d * 100, 2),
            "avg_attempt_cost": int(avg_cost),
            "avg_sell_price": int(avg_sell),
            "cost_to_reach": int(prev_cum_cost),
            "expected_profit": int(expected_profit),
            "sigma_cost": int(std_dev_cost),
            "mean_attempts": int(mean_attempts),
            "time_efficiency": int(time_efficiency),
            "cumulative_prob": round(cumulative_prob * 100, 6),  # 백분율로 저장
            "pure_success_prob": round(pure_success_prob * 100, 6)  # 유지 무시 순수 성공 확률
        }
        analysis_out.append(row)

    # CORS때문에 JS로 저장
    js_content = f"const swordData = {json.dumps(analysis_out, indent=4, ensure_ascii=False)};"
    
    js_file = os.path.join(STAT_DIR, "data.js")
    with open(js_file, 'w', encoding='utf-8') as f:
        f.write(js_content)
        
    print(f"Analysis complete. Saved to {js_file}")

if __name__ == "__main__":
    analyze()
