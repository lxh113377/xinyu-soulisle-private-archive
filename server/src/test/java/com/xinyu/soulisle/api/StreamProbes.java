package com.xinyu.soulisle.api;

import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * r168（S3）流式时序断言的两个探针，替 {@code ChatControllerTest} 把「边生成边下发」这件事量出来。
 *
 * <p>单独成文件而不是当内部类：本仓 {@code _test/loc_guard_check.py} 按花括号深度量函数长，
 * 内部类里的数组初始化 {@code new byte[] {…}} 会让深度从某个方法起一路不归零，
 * 把 190 行的测试类算成「最长函数 253 行」并把整个文件顶成 enforce 红（r168 一手实测）。
 * 拆开既是给判据让路，也是让「探针」与「断言」各归其位 —— 断言读起来该只有断言。
 *
 * <p>两个探针都不联网、不需要密钥，只在内存里挪字节；上游侧的关键设计见 {@link Trickler}。
 */
final class StreamProbes {

    private StreamProbes() {
    }

    /** 写侧记录仪：把 write/flush 记成事件序列（W=一次写、F=一次 flush），供时序断言使用。 */
    static final class Recorder extends OutputStream {

        final List<String> events = new ArrayList<>();
        private final StringBuilder text = new StringBuilder();
        int writes;
        int flushes;

        @Override
        public void write(int b) {
            byte[] one = new byte[1];
            one[0] = (byte) b;
            write(one, 0, 1);
        }

        @Override
        public void write(byte[] b, int off, int len) {
            writes++;
            events.add("W" + len);
            text.append(new String(b, off, len, StandardCharsets.UTF_8));
        }

        @Override
        public void flush() {
            flushes++;
            events.add("F");
        }

        String body() {
            return text.toString();
        }
    }

    /**
     * 只在被再次 read 时才产出下一块的假上游 —— 用它把「先下发、后取下一块」的时序逼出来。
     *
     * <p>{@link #secondReadSeenFlushes} 是这块尺的牙：它在**取第二块之前**那一刻记下写侧已经
     * flush 过几次。攒完整段再一把 flush 的写法会给出 0，逐块下发的写法给出 ≥1。
     */
    static final class Trickler extends InputStream {

        private final String[] chunks;
        private final Recorder sink;
        private int index;
        private int pos;
        int secondReadSeenFlushes = -1;

        Trickler(String[] chunks, Recorder sink) {
            this.chunks = chunks;
            this.sink = sink;
        }

        @Override
        public int read() {
            byte[] one = new byte[1];
            int n = read(one, 0, 1);
            return n < 0 ? -1 : (one[0] & 0xff);
        }

        @Override
        public int read(byte[] b, int off, int len) {
            if (index == 1 && pos == 0) {
                secondReadSeenFlushes = sink.flushes;
            }
            byte[] src = currentChunk();
            if (src == null) {
                return -1;
            }
            int n = Math.min(src.length - pos, len);
            System.arraycopy(src, pos, b, off, n);
            pos += n;
            if (pos < src.length) {
                return n;
            }
            pos = 0;
            index++;
            return n;
        }

        private byte[] currentChunk() {
            if (index >= chunks.length) {
                return null;
            }
            return chunks[index].getBytes(StandardCharsets.UTF_8);
        }
    }
}
