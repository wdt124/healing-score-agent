### 核心调用接口

import json
import os
import warnings
import numpy as np
import joblib
import librosa
import dashscope
from dashscope import Generation
from http import HTTPStatus

# 忽略 librosa 可能产生的某些库警告，保持控制台干净
warnings.filterwarnings('ignore')

class UnifiedDepressionEngine:
    """
    自适应抑郁风险打分引擎 (Unified Depression Scoring Engine)
    内部封装 V1(纯文本) 与 V2(多模态) 双模型，对外提供统一调用接口。
    """
    def __init__(self, v1_model_path='eatd_rf_model_v1.joblib', v2_model_path='eatd_multimodal_rf_model_v2.joblib', api_key=None):
        print("⚙️ 正在初始化 UnifiedDepressionEngine...")
        
        # 1. 加载双脑模型
        if not os.path.exists(v1_model_path) or not os.path.exists(v2_model_path):
            raise FileNotFoundError("找不到模型文件，请确保 .joblib 文件在当前目录下！")
            
        self.text_scorer_v1 = joblib.load(v1_model_path)
        self.multimodal_scorer_v2 = joblib.load(v2_model_path)
        
        # 2. 配置通义千问 API 密钥
        if api_key:
            dashscope.api_key = api_key
            
        # 强制特征顺序列表 (严禁修改顺序)
        self.TEXT_FEATURE_KEYS = ["anhedonia", "depressed", "sleep", "fatigue", "appetite", "guilt", "concentrate", "movement"]

    def _extract_text_features(self, text):
        """
        调用 Qwen 提取 8 维文本病理特征
        """
        system_prompt = """你是一位专业的临床心理学家。请分析用户的文本，并在以下8个抑郁维度上进行打分（0=无，1=轻度，2=中度，3=重度）。
        必须严格输出纯JSON格式，不要任何Markdown包裹（如```json），包含且仅包含以下键：
        "anhedonia", "depressed", "sleep", "fatigue", "appetite", "guilt", "concentrate", "movement"."""
        
        try:
            response = Generation.call(
                model="qwen-plus", 
                messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': text}],
                result_format='message'
            )
            
            if response.status_code == HTTPStatus.OK:
                clean_content = response.output.choices[0]['message']['content'].strip()
                # 清理可能残留的 markdown 标记
                if clean_content.startswith("```json"):
                    clean_content = clean_content[7:-3].strip()
                elif clean_content.startswith("```"):
                    clean_content = clean_content[3:-3].strip()
                    
                return json.loads(clean_content)
        except Exception as e:
            print(f"⚠️ 文本特征提取失败，启用安全降级机制: {e}")
            
        # 如果大模型调用失败或解析错误，返回全 0 的安全底线
        return {k: 0 for k in self.TEXT_FEATURE_KEYS}

    def _extract_audio_features(self, audio_path):
        """
        调用 librosa 提取 17 维声学特征
        """
        try:
            y, sr = librosa.load(audio_path, sr=16000)
            
            # 1. 提取 F0 (基频) 均值与标准差
            f0, _, _ = librosa.pyin(y, fmin=65, fmax=2000)
            f0 = f0[~np.isnan(f0)] 
            f0_mean = np.mean(f0) if len(f0) > 0 else 0
            f0_std = np.std(f0) if len(f0) > 0 else 0
            
            # 2. 提取 RMS (能量/气力) 均值与标准差
            rms = librosa.feature.rms(y=y)
            rms_mean = np.mean(rms)
            rms_std = np.std(rms)
            
            # 3. 提取 MFCC (音色/声道) 1-13 均值
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfcc_mean_list = np.mean(mfcc, axis=1).tolist()
            
            # 严格拼接为 17 维数组
            return [f0_mean, f0_std, rms_mean, rms_std] + mfcc_mean_list
            
        except Exception as e:
            print(f"⚠️ 音频特征提取失败，返回全 0 数组: {e}")
            return [0] * 17

    def predict(self, text, audio_path=None):
        """
        🚀 核心对外接口：智能路由分发
        - 仅传 text -> 走 V1 文本大脑
        - 传 text + audio_path -> 走 V2 多模态大脑
        """
        # 1. 提取语义特征 (始终执行)
        text_json = self._extract_text_features(text)
        text_feats_list = [text_json.get(k, 0) for k in self.TEXT_FEATURE_KEYS]

        # 2. 智能路由逻辑
        if audio_path is None or not os.path.exists(audio_path):
            # -------- 启用 V1 引擎 --------
            final_score = self.text_scorer_v1.predict([text_feats_list])[0]
            used_model = "V1_Text_Only"
            audio_diagnostics = "No audio input detected"
        else:
            # -------- 启用 V2 引擎 --------
            audio_feats_list = self._extract_audio_features(audio_path)
            fused_features = text_feats_list + audio_feats_list
            final_score = self.multimodal_scorer_v2.predict([fused_features])[0]
            
            used_model = "V2_Multimodal"
            audio_diagnostics = {
                "pitch_mean_hz": round(audio_feats_list[0], 2),
                "energy_mean": round(audio_feats_list[2], 4)
            }

        # 3. 封装标准返回体
        risk_level = "重度" if final_score >= 73 else "中度" if final_score >= 63 else "轻度" if final_score >= 53 else "正常"
        
        return {
            "status": "success",
            "engine_used": used_model,
            "predicted_sds_score": round(final_score, 2),
            "risk_level": risk_level,
            "details": {
                "text_features_extracted": text_json,
                "audio_features_summary": audio_diagnostics
            }
        }