package com.xinyu.soulisle.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.xinyu.soulisle.entity.ChatMessage;
import com.xinyu.soulisle.entity.EmotionRecord;
import com.xinyu.soulisle.mapper.ChatMessageMapper;
import com.xinyu.soulisle.mapper.EmotionRecordMapper;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 记忆持久化（J4）：把原先只存在浏览器 localStorage 的对话历史与情绪记录搬到服务端。
 *
 * <p>前端仍保留本地存储作为降级路径（服务端不可达时照常工作），此处是权威副本。
 */
@Service
public class MemoryService {

    private static final int MAX_LIMIT = 500;

    private final EmotionRecordMapper emotionMapper;
    private final ChatMessageMapper messageMapper;

    public MemoryService(EmotionRecordMapper emotionMapper, ChatMessageMapper messageMapper) {
        this.emotionMapper = emotionMapper;
        this.messageMapper = messageMapper;
    }

    public void addEmotion(String sessionId, String emotion, double intensity, String secondary, String text) {
        EmotionRecord r = new EmotionRecord();
        r.setSessionId(sessionId);
        r.setEmotion(emotion);
        r.setIntensity(intensity);
        r.setSecondary(secondary);
        r.setText(text == null ? "" : clamp(text, 200));
        r.setCreatedAt(LocalDateTime.now());
        emotionMapper.insert(r);
    }

    /** 返回按时间正序的最后 limit 条（内部先倒序取，再反转，避免全表扫后截断） */
    public List<EmotionRecord> emotions(String sessionId, int limit) {
        List<EmotionRecord> list = emotionMapper.selectList(
                Wrappers.<EmotionRecord>lambdaQuery()
                        .eq(EmotionRecord::getSessionId, sessionId)
                        .orderByDesc(EmotionRecord::getId)
                        .last("LIMIT " + normLimit(limit)));
        List<EmotionRecord> out = new ArrayList<>(list);
        Collections.reverse(out);
        return out;
    }

    public void addMessage(String sessionId, String role, String content) {
        ChatMessage m = new ChatMessage();
        m.setSessionId(sessionId);
        m.setRole(role);
        m.setContent(content == null ? "" : clamp(content, 2000));
        m.setCreatedAt(LocalDateTime.now());
        messageMapper.insert(m);
    }

    public List<ChatMessage> messages(String sessionId, int limit) {
        List<ChatMessage> list = messageMapper.selectList(
                Wrappers.<ChatMessage>lambdaQuery()
                        .eq(ChatMessage::getSessionId, sessionId)
                        .orderByDesc(ChatMessage::getId)
                        .last("LIMIT " + normLimit(limit)));
        List<ChatMessage> out = new ArrayList<>(list);
        Collections.reverse(out);
        return out;
    }

    /** 一键清除（对应前端「清除我的数据」） */
    public int clear(String sessionId) {
        int a = emotionMapper.delete(Wrappers.<EmotionRecord>lambdaQuery().eq(EmotionRecord::getSessionId, sessionId));
        int b = messageMapper.delete(Wrappers.<ChatMessage>lambdaQuery().eq(ChatMessage::getSessionId, sessionId));
        return a + b;
    }

    public long countEmotions(String sessionId) {
        return emotionMapper.selectCount(
                Wrappers.<EmotionRecord>lambdaQuery().eq(EmotionRecord::getSessionId, sessionId));
    }

    public long countMessages(String sessionId) {
        return messageMapper.selectCount(
                Wrappers.<ChatMessage>lambdaQuery().eq(ChatMessage::getSessionId, sessionId));
    }

    private int normLimit(int limit) {
        if (limit <= 0) {
            return 200;
        }
        return Math.min(limit, MAX_LIMIT);
    }

    private String clamp(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max);
    }
}
