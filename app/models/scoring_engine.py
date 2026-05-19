###
# predicted_sds_score >= 73 -> high ,
# predicted_sds_score >= 63 -> medium ,
# predicted_sds_score >= 53 -> low ,
# predicted_sds_score < 53 -> normal .

import os
import warnings
import numpy as np
import joblib
import librosa
from typing_extensions import TypedDict, Annotated
from langchain_openai import ChatOpenAI
from app.core.config import settings

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

class UnifiedDepressionEngine:
    """
    自适应抑郁风险打分引擎 (Unified Depression Scoring Engine)
    内部封装 V1(纯文本) 与 V2(多模态) 双模型，对外提供统一调用接口。
    """
    def __init__(self, v1_model_path='eatd_rf_model_v1.joblib', v2_model_path='eatd_multimodal_rf_model_v2.joblib'):
        print("正在初始化 UnifiedDepressionEngine...")
        
        # 1. 加载双脑模型
        if not os.path.exists(v1_model_path) or not os.path.exists(v2_model_path):
            raise FileNotFoundError("找不到模型文件，请确保 .joblib 文件在当前目录下！")
            
        self.text_scorer_v1 = joblib.load(v1_model_path)
        self.multimodal_scorer_v2 = joblib.load(v2_model_path)
        
        # 2. 配置 API 密钥
        self.model = ChatOpenAI(
            model='deepseek-chat',
            api_key=settings.api_key,
            base_url=settings.base_url,
            temperature=0.0
        )

        # 强制特征顺序列表
        self.TEXT_FEATURE_KEYS = ["anhedonia", "depressed", "sleep", "fatigue", "appetite", "guilt", "concentrate", "movement"]

    def _extract_text_features(self, text):
        """
        调用 DeepSeek 提取 8 维文本病理特征
        """

        system_prompt = """你是一位专业的临床心理学家。请分析用户的文本，并在以下8个抑郁维度上进行打分（0=无，1=轻度，2=中度，3=重度）。
        必须严格输出纯JSON格式，包含且仅包含以下键：
        "anhedonia", "depressed", "sleep", "fatigue", "appetite", "guilt", "concentrate", "movement"."""

        try:
            # 绑定结构化输出工具 (LangChain 会自动处理 schema 和强制返回格式)
            structured_llm = self.model.with_structured_output(VctDict)

            # 组装消息并调用
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]

            # 返回的结果直接就是一个符合 VctDict 结构的字典
            result = structured_llm.invoke(messages)
            return result

        except Exception as e:
            # 捕获所有 API 异常或结构化解析异常
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


        return {
            "status": "success",
            "engine_used": used_model,
            "predicted_sds_score": round(final_score, 2),
            "details": {
                "text_features_extracted": text_json,
                "audio_features_summary": audio_diagnostics
            }

        }