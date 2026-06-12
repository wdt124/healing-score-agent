import os
import warnings
import json
import numpy as np
import joblib
import librosa
from typing_extensions import TypedDict, Annotated
from app.core.llm_client import LLMClientManager

# 忽略 librosa 可能产生的某些库警告，保持控制台干净
warnings.filterwarnings('ignore')

class VctDict(TypedDict):
    anhedonia: Annotated[int, "请分析用户的文本，并在anhedonia抑郁维度上进行打分（0=无，1=轻度，2=中度，3=重度）"]
    depressed: Annotated[int, "请分析用户的文本，并在depressed抑郁维度上进行打分（0=无，1=轻度，2=中度，3=重度）"]
    sleep: Annotated[int, "请分析用户的文本，并在sleep抑郁维度上进行打分（0=无，1=轻度，2=中度，3=重度）"]
    fatigue: Annotated[int, "请分析用户的文本，并在fatigue抑郁维度上进行打分（0=无，1=轻度，2=中度，3=重度）"]
    appetite: Annotated[int, "请分析用户的文本，并在appetite抑郁维度上进行打分（0=无，1=轻度，2=中度，3=重度）"]
    guilt: Annotated[int, "请分析用户的文本，并在guilt抑郁维度上进行打分（0=无，1=轻度，2=中度，3=重度）"]
    concentrate: Annotated[int, "请分析用户的文本，并在concentrate抑郁维度上进行打分（0=无，1=轻度，2=中度，3=重度）"]
    movement: Annotated[int, "请分析用户的文本，并在movement抑郁维度上进行打分（0=无，1=轻度，2=中度，3=重度）"]
    ai_sds_score: Annotated[float, "基于全局直觉给出一个预测的 SDS 抑郁标准分（范围 25.0 到 100.0）"]

class UnifiedDepressionEngine:
    """
    自适应多模态抑郁风险打分引擎 (Unified Depression Scoring Engine) V2
    内部封装 V1(文本+AI分) 与 V2(多模态26维) 双模型，对外提供统一调用接口。
    """
    def __init__(self, v1_model_path='eatd_rf_model_v1.joblib', v2_model_path='eatd_multimodal_rf_model_v2.joblib'):
        print("正在初始化新版 UnifiedDepressionEngine (支持26维多模态融合)...")
        
        # 1. 加载双脑模型
        if not os.path.exists(v1_model_path) or not os.path.exists(v2_model_path):
            raise FileNotFoundError(f"找不到模型文件，请确保 {v1_model_path} 和 {v2_model_path} 在对应目录下！")
            
        self.text_scorer_v1 = joblib.load(v1_model_path)
        self.multimodal_scorer_v2 = joblib.load(v2_model_path)
        
        # 2. 获取评分专用 LLM 客户端 (temperature=0.0)
        self.model = LLMClientManager.get_scoring_client()

        # 核心文本症状基础键名（前8维）
        self.TEXT_FEATURE_KEYS = ["anhedonia", "depressed", "sleep", "fatigue", "appetite", "guilt", "concentrate", "movement"]

    def _extract_text_features(self, text):
        """
        调用 LLM 提取 8 维文本病理特征 + 1 维 AI 全局标准分 (共 9 维)
        """
        system_prompt = """你是一位专业的临床心理学家。请阅读用户的文本，完成以下两项量化评估：
        1. 评估其在8个特定抑郁维度上的表现，评分限制在0、1、2、3（0=无，1=轻度，2=中度，3=重度）。
        2. 基于全局直觉给出一个预测的 SDS 抑郁标准分（ai_sds_score，范围 25.0 到 100.0）。
        
        必须严格输出纯 JSON 格式，包含且仅包含指定结构的 9 个键：
        "anhedonia", "depressed", "sleep", "fatigue", "appetite", "guilt", "concentrate", "movement", "ai_sds_score"."""

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]

            response = self.model.invoke(messages)
            result = json.loads(response.content)
            expected_keys = self.TEXT_FEATURE_KEYS + ["ai_sds_score"]
            for k in expected_keys:
                if k not in result:
                    result[k] = 0 if k != "ai_sds_score" else 50.0
            return result

        except Exception as e:
            print(f"⚠️ 文本特征提取失败，启用安全降级机制: {e}")

    
        fallback = {k: 0 for k in self.TEXT_FEATURE_KEYS}
        fallback["ai_sds_score"] = 50.0
        return fallback

    def _extract_audio_features(self, audio_path):
        """
        调用 librosa 提取 17 维声学特征
        """
        try:
            y, sr = librosa.load(audio_path, sr=16000)
            
            # 1. 提取 F0 (基频/音调) 均值与标准差
            f0, _, _ = librosa.pyin(y, fmin=65, fmax=2000)
            f0 = f0[~np.isnan(f0)] 
            f0_mean = np.mean(f0) if len(f0) > 0 else 0
            f0_std = np.std(f0) if len(f0) > 0 else 0
            
            # 2. 提取 RMS (能量/气力) 均值与标准差
            rms = librosa.feature.rms(y=y)
            rms_mean = np.mean(rms)
            rms_std = np.std(rms)
            
            # 3. 提取 MFCC (音色/声道辨识) 1-13 维均值
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfcc_mean_list = np.mean(mfcc, axis=1).tolist()
            
            # 严格拼接为 17 维声学特征数组
            return [f0_mean, f0_std, rms_mean, rms_std] + mfcc_mean_list
            
        except Exception as e:
            print(f"⚠️ 音频特征提取失败，返回全 0 声学数组: {e}")
            return [0] * 17

    def predict(self, text, audio_path=None):
        """
        🚀 核心对外接口：智能多模态路由分发
        - 仅传 text -> 组合出 9 维特征列表 -> 走升级版 V1 纯文本大脑
        - 传 text + audio_path -> 组合出 26 维特征列表 -> 走 V2 多模态全融合大脑
        """
        # 1. 提取文本+预测特征 (包含 8维症状 + 1维ai_sds_score)
        text_json = self._extract_text_features(text)
        
        # 严格按照标准顺序组装前 8 维
        text_feats_8 = [text_json.get(k, 0) for k in self.TEXT_FEATURE_KEYS]
        # 获取第 9 维 AI 评分
        ai_score = text_json.get("ai_sds_score", 50.0)

        # 2. 智能路由与特征对齐逻辑
        if audio_path is None or not os.path.exists(audio_path):
            # -------- 启用升级版 V1 文本大脑 (9维) --------
            v1_features = text_feats_8 + [ai_score]
            final_score = self.text_scorer_v1.predict([v1_features])[0]
            
            used_model = "V1_Text_With_AiScore"
            audio_diagnostics = "No audio input detected or file missing"
        else:
            # -------- 启用 V2 多模态全融合大脑 (26维: 8 + 1 + 17) --------
            audio_feats_list = self._extract_audio_features(audio_path)
            
            # 严格按照 [8维文本症状] + [1维AI全局分] + [17维声学特征] 进行平铺拼接
            fused_features = text_feats_8 + [ai_score] + audio_feats_list
            
            final_score = self.multimodal_scorer_v2.predict([fused_features])[0]
            
            used_model = "V2_Multimodal_26Dim"
            audio_diagnostics = {
                "pitch_mean_hz": round(audio_feats_list[0], 2),
                "pitch_std_hz": round(audio_feats_list[1], 2),
                "energy_mean": round(audio_feats_list[2], 4),
                "mfcc_baseline": round(audio_feats_list[4], 4)  # 打印 MFCC_1 作为监控参考
            }

        return {
            "status": "success",
            "engine_used": used_model,
            "predicted_sds_score": round(final_score, 2),
            "details": {
                "text_features_extracted": text_json,
                "audio_features_summary": audio_diagnostics
            }
        }