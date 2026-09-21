package com.xinyu.soulisle.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

import java.time.LocalDateTime;

/** 情绪记录（J4）：替代前端 localStorage 的 `peiliao.emotions.v1` */
@TableName("emotion_record")
public class EmotionRecord {

    @TableId(type = IdType.AUTO)
    private Long id;
    private String sessionId;
    private String emotion;
    private Double intensity;
    private String secondary;
    private String text;
    private LocalDateTime createdAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }

    public String getEmotion() { return emotion; }
    public void setEmotion(String emotion) { this.emotion = emotion; }

    public Double getIntensity() { return intensity; }
    public void setIntensity(Double intensity) { this.intensity = intensity; }

    public String getSecondary() { return secondary; }
    public void setSecondary(String secondary) { this.secondary = secondary; }

    public String getText() { return text; }
    public void setText(String text) { this.text = text; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
