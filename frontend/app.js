/* SonicForge workspace.
   MediaForge と同じ組み立て方をする。ホストの handshake でテーマ・ロケール・
   セーフエリアを受け取り、表示は「シンプル / 詳細」の 2 段だけに畳む。
   詳細だけの断片は <template> から差し込み、シンプルでは DOM から外す。 */

const I18N = {
  ja: {
    localOnlyHint: "音声の生成と文字起こしはこの端末の中だけで実行されます",
    localOnly: "ローカルのみ",
    displayMode: "表示モード",
    modeSimple: "シンプル",
    modeAdvanced: "詳細",
    settings: "設定",
    settingsTitle: "ランタイムとボイスの設定",
    studio: "スタジオ",
    library: "ライブラリ",
    activity: "状況",
    pipeline: "パイプライン",

    whatToMake: "作るもの",
    taskSpeech: "音声",
    taskTranscribe: "文字起こし",
    taskSfx: "効果音",
    taskMusic: "音楽",
    taskLocalization: "ローカライズ",
    taskMeeting: "会議",
    taskChat: "会話",
    summarySpeech: "書いた文章を、選んだ声で読み上げます。",
    summaryTranscribe: "音声ファイルから文字を起こします。",
    summarySfx: "説明した音を、短い効果音として作ります。",
    summaryMusic: "説明した雰囲気のBGMを作ります。",
    summaryLocalization: "日本語と英語のセリフをまとめて生成します。",
    summaryMeeting: "話している内容をその場で文字にして残します。",
    summaryChat: "話しかけると、AIが声で答えます。",

    speechTextLabel: "読み上げるテキスト",
    speechStyle: "話し方",
    contentLanguage: "言語",
    speechLanguageLabel: "読み上げる言語",
    transcribeLanguageLabel: "話されている言語",
    voice: "ボイス",
    ttsEngine: "音声エンジン",
    ttsQwen: "Qwen3-TTS（組み込み音声・ボイス設計）",
    ttsGptSovits: "GPT-SoVITS（高速・参照音声）",
    ttsEngineSaved: "この選択は保存され、次回以降のTTSにも使われます。",
    gptVoiceRequired: "GPT-SoVITSではクローン音声、または参照音声付きモデルを選んでください。",
    builtInVoice: "組み込みボイス（おまかせ）",
    audioFile: "音声ファイル",
    chooseAudio: "＋ 音声ファイルを選ぶ",
    clearFile: "使わない",
    sfxPromptLabel: "どんな音ですか？",
    sfxKind: "音の種類",
    musicPromptLabel: "どんな曲ですか？",
    musicMood: "雰囲気",
    length: "長さ",
    instrumental: "歌なし（BGM）",
    create: "作る",
    creating: "作っています…",
    transcribeAction: "文字起こしする",
    resetForm: "入力と設定を初期に戻す",
    refresh: "一覧を更新",
    filter: "絞り込み",

    auto: "自動",
    japanese: "日本語",
    english: "English",
    quality: "品質",
    qualityFast: "速さ優先",
    qualityBalanced: "おすすめ",
    qualityHigh: "品質優先",

    styleAuto: "おまかせ",
    styleGentle: "やさしく",
    styleBright: "元気に",
    styleCalm: "落ち着いて",
    styleNarration: "ナレーション",

    sfxUi: "UI音",
    sfxImpact: "打撃・衝撃",
    sfxMechanical: "機械",
    sfxMagic: "魔法・SF",
    sfxFoley: "足音・生活音",
    sfxAmbience: "環境音",
    sfxCustom: "指定しない",

    moodAuto: "おまかせ",
    moodCalm: "静か・落ち着いた",
    moodEnergetic: "明るい・元気",
    moodTense: "緊張感",
    moodEpic: "壮大",
    moodRetro: "レトロ",

    bpmSlow: "ゆっくり",
    bpmMedium: "標準",
    bpmFast: "速い",
    bpmNone: "指定しない",

    advancedCommon: "共通の詳細設定",
    advancedSpeech: "読み上げの詳細設定",
    advancedTranscribe: "文字起こしの詳細設定",
    advancedTranscribeHint: "区切りと時刻は、この機材で採用されている経路が返せる範囲で結果に含まれます。",
    advancedSfx: "効果音の詳細設定",
    advancedMusic: "音楽の詳細設定",
    advancedRouting: "エンジンの指定",
    advancedRoutingHint: "空欄なら、この機材で最も確実な経路を自動で選びます。",
    advancedOutputTarget: "書き出し先",
    outputFormat: "出力形式",
    sampleRate: "サンプルレート",
    channels: "チャンネル",
    profileName: "プロファイル名",
    engine: "エンジン",
    model: "モデル",
    modelAuto: "おまかせ（自動で選ぶ）",
    modelKotoba: "日本語に強い（kotoba-whisper v2.0）",
    modelWhisperTurbo: "多言語（whisper large v3 turbo）",
    modelQwenCustom: "標準の読み上げ（Qwen3-TTS 0.6B）",
    modelQwenDesign: "声のデザイン向け（Qwen3-TTS 1.7B）",
    modelStableAudio: "効果音（Stable Audio 3 Small SFX）",
    modelAceStep: "音楽（ACE-Step 1.5 Turbo）",
    modelNoteVoice: "保存したボイスを選んでいるときは、そのボイスが作られたモデルを使います。",
    modelNoteSingle: "この機能で使えるモデルは今ひとつだけです。",
    modelNoteMissing: "この機能はまだ準備できていません。設定から準備してください。",
    device: "デバイス",
    seed: "シード",
    styleInstruction: "話し方の指示（自由文）",
    styleInstructionHint: "上の「話し方」プリセットより優先されます。空欄ならプリセットを使います。",
    timestamps: "区切りごとの時刻を表示する",
    lengthSeconds: "長さ（秒）",
    bpm: "テンポ（BPM）",
    sfxAmbienceHint: "「環境音」を選ぶと、単発の効果音ではなく持続する環境音として生成します。",
    chooseProjectOutput: "＋ 書き出し先を選ぶ",
    projectOutputHint: "選ぶと、できあがった音声をControlDeckのプロジェクトにも保存します。",
    projectOutputSelected: "書き出し先を選びました。",
    promptPreview: "送信する説明",

    preparing: "準備しています",
    running: "生成しています",
    queued: "順番を待っています",
    done: "できあがりました",
    failed: "できませんでした",
    canceled: "中止しました",
    cancel: "中止",
    makeAnother: "もう一度作る",
    exportAsset: "書き出す",
    details: "詳細",
    close: "閉じる",
    back: "戻る",
    save: "保存",
    delete: "削除する",
    recent: "最近作ったもの",
    recentEmpty: "まだ何もありません。作りたいものを書いて「作る」を押してください。",
    noJobs: "実行中・完了した処理はありません。",
    libraryEmpty: "まだ音声がありません。",

    exportTitle: "音声を書き出す",
    exportProfile: "書き出しプロファイル",
    filename: "ファイル名",
    exportToProject: "ControlDeckのプロジェクトへ書き出す",
    exportStarted: "書き出しを開始しました。",

    runtimeTitle: "利用できる機能",
    runtimeHint: "必要なものだけを、必要になったときに準備します。音声を使うだけなら「音声基本環境」だけで足ります。",
    setupPlan: "準備の内訳とハードウェア",
    setupProfile: "まとめて準備する",
    setupStart: "この内容で準備する",
    recheck: "内訳を確認",
    setUp: "セットアップ",
    repair: "修復",
    update: "更新",
    openSetup: "セットアップを開く",
    setupRequired: "この機能にはセットアップが必要です",
    componentGptSovits: "GPT-SoVITS",
    componentGptSovitsDetail: "高速な参照音声ベースの読み上げ。Qwen3-TTSとは別環境に導入します。",
    profileGptSovits: "GPT-SoVITSだけ",
    ttsModelsTitle: "GPT-SoVITS モデル",
    ttsModelsHint: "manifest.json付きZIPを検査して展開します。モデルの権利・ライセンス・入手元の記載が必要です。",
    ttsModelFormat: "ZIP の manifest.json 形式",
    ttsModelUpload: "ZIPを追加",
    ttsModelActivate: "使う",
    ttsModelActive: "使用中",
    ttsModelDeleteActive: "使用中のモデルは削除できません。先に別のモデルへ切り替えてください。",
    ttsModelDeleteBody: "モデル本体と管理情報を削除します。この操作は取り消せません。",
    gptSampleName: "サンプル音声名",
    gptSampleLanguage: "言語",
    gptSampleText: "音声の正確な書き起こし",
    gptSampleAdd: "サンプル音声を登録",
    gptSampleRequired: "名前、音声、正確な書き起こし、権利確認が必要です。",
    gptSampleSelect: "登録したサンプル音声を選択",
    gptReference: "参照サンプル（ボイスクローン）",
    gptReferenceAdd: "＋ サンプルを追加",
    gptReferenceNote: "3〜10秒の参照音声、または参照音声付き学習済みモデルで推論します。Qwenの話者種類は使いません。",
    gptSamplePreset: "参照サンプル",
    gptSampleCustom: "自分の音声（ローカルファイル）",
    gptSampleLocalHint: "配布元から音声を取得し、下でそのWAVを選んでください。音声ファイルへの直リンクは行いません。",
    gptSampleManagedHint: "配布元・改訂・SHA-256を固定した参照音声をダウンロードして保存します。",
    gptSampleSource: "配布元",
    gptSampleTerms: "利用規約",
    gptSampleAcceptTerms: "配布元の利用規約を確認し、この端末へ導入して利用することに同意します",
    gptSampleUse: "このサンプルを選択",
    componentCore: "SonicForge本体",
    componentSpeech: "音声基本環境",
    componentSpeechDetail: "日本語・英語の音声合成と文字起こし",
    componentGame: "ゲーム音声",
    componentGameDetail: "効果音と環境音の生成（Stable Audio 3 Small-SFX）",
    componentMusic: "音楽生成",
    componentMusicDetail: "BGMと楽曲の生成（ACE-Step 1.5）",
    profileSpeech: "音声基本環境だけ",
    profileGame: "ゲーム音声を追加",
    profileMusic: "音楽生成を追加",
    profileFull: "すべて（フルスタジオ）",
    profileCpu: "CPUだけで動く構成",
    termsStability: "Stability AI Community Licenseを確認し、同意しました",
    termsRequired: "先にライセンスへの同意が必要です。",
    displayLanguage: "表示言語",
    displayLanguageHint: "ControlDeckの言語にあわせています。ここで変えるとこの画面だけに効きます。",
    backend: "演算バックエンド",
    freeSpace: "空き容量",
    requiredSpace: "必要な容量の見込み",
    platform: "プラットフォーム",
    blockers: "準備できない理由",
    diagnostics: "診断情報",
    capabilityDetail: "機能ごとの状態",

    voicesTitle: "ボイス",
    voicesHint: "同じ話し手を何度も使うために覚えさせておけます。スタジオの「音声」で選べます。",
    voicesEmpty: "まだ登録がありません。組み込みボイスがそのまま使えます。",
    voiceAdd: "＋ ボイスを作る",
    voiceKind: "作り方",
    voiceBuiltIn: "組み込みの声を選ぶ",
    voiceDesign: "声を言葉でデザインする",
    voiceClone: "参照音声から作る",
    voiceBuiltInHint: "用意されている話者から選びます。権利の確認は要りません。",
    voiceDesignHint: "どんな声かを言葉で書くと、その特徴に寄せた声を作ります。",
    voiceCloneHint: "手元の音声に似せた声を作ります。利用する権利があることの確認が要ります。",
    voiceSpeaker: "話者",
    voiceInstruction: "声の説明",
    voiceReference: "参照音声",
    voiceReferenceText: "参照音声の書き起こし（任意）",
    voiceLanguages: "使う言語",
    voiceRights: "この音声を利用・複製する権利があることを確認します",
    voiceRightsRequired: "権利の確認にチェックが必要です。",
    name: "名前",
    nameRequired: "名前を入力してください。",
    deleteVoiceTitle: "このボイスを削除しますか？",
    deleteVoiceBody: "このボイスを使った既存の音声は残りますが、これ以降は選べなくなります。",

    devicesTitle: "音声エージェント端末",
    devicesHint: "M5などの小型端末をControlDeck経由でペアリングします。端末側のファームウェアはここでは扱いません。",
    deviceLabel: "端末の名前",
    deviceRelay: "中継",
    devicePair: "ペアリングを作る",

    pipelineTitle: "音声パイプライン",
    pipelineHint: "文字起こし・ControlDeckのAI・読み上げ・効果音・音楽を、順番につないで一度に実行します。",
    pipelinePreset: "よく使う組み合わせ",
    pipelineInput: "入力",
    pipelineStages: "処理の並び",
    pipelineDelivery: "受け取り方",
    startAt: "開始する段",
    stopAfter: "終了する段",
    deliveryMode: "形式",
    validate: "組み合わせを確認",
    run: "実行",
    fromLibrary: "ライブラリから選ぶ",
    inputText: "文章",
    inputFile: "音声ファイル",
    inputAsset: "ライブラリの音声",
    stageAsr: "文字起こし",
    stageAi: "ControlDeckのAI",
    stageTts: "読み上げ",
    stageSfx: "効果音",
    stageMusic: "音楽",
    stageProcess: "音声の整形",
    deliveryText: "文字だけ受け取る",
    deliveryAsset: "ライブラリに保存",
    deliveryProject: "プロジェクトへ書き出す",
    presetDub: "文字起こし → 翻訳 → 読み上げ",
    presetTranscribe: "文字起こしだけ",
    presetSpeak: "読み上げだけ",
    presetRewrite: "文字起こし → 要約",
    presetChat: "音声チャット（話す → AIの返事 → 読み上げ）",
    pipelineValid: "この組み合わせで実行できます",
    pipelineOutputText: "受け取るのは文字です",
    pipelineOutputAudio: "受け取るのは音声です",

    localizationTitle: "ローカライズスタジオ",
    localizationHint: "1行につき「ID | キャラクター | 日本語 | English」を入力します。CSVを貼り付けても構いません。",
    batchName: "バッチ名",
    createBatch: "バッチを作って生成",
    openBatch: "既存のバッチを開く",
    renderPending: "未生成を生成",
    renderFailed: "失敗のみ再生成",
    renderChanged: "変更のみ再生成",
    renderAll: "すべて再生成",
    filenamePattern: "ファイル名の付け方",
    lineId: "ID",
    character: "キャラクター",
    status: "状態",
    locales: "生成する言語",
    noLines: "行がありません。上のテキスト欄に入力してください。",

    meetingTitle: "会議の文字起こし",
    meetingHint: "マイクの音声をその場で文字にします。翻訳と要約はControlDeckのAIを使います。",
    meetingStart: "録音を開始",
    meetingStop: "停止して仕上げる",
    meetingRecording: "録音中",
    meetingTitleField: "会議名",
    meetingTranslate: "翻訳する",
    meetingSummarize: "終わったら要約する",
    meetingTargetLanguage: "翻訳先",
    meetingChunk: "区切りの長さ（秒）",
    meetingPast: "これまでの会議",
    meetingNoPast: "まだ記録がありません。",
    meetingTranscript: "全文を開く",
    meetingMicDenied: "マイクを使えませんでした。ブラウザでマイクの利用を許可してください。",
    meetingMicUnsupported: "このブラウザではマイクからの録音に対応していません。",
    meetingSummary: "要約",

    stateAvailable: "利用可能",
    statePreparing: "準備中",
    stateSetupRequired: "セットアップが必要",
    stateUnavailable: "利用不可",
    stateFailed: "失敗",
    stateQueued: "待機中",
    stateRunning: "実行中",
    stateSucceeded: "完了",
    stateCanceled: "中止",
    provenance: "生成の記録",
    audioAsset: "音声",
    aiInstruction: "AIへの指示",
    inputLevel: "入力レベル",
    itemCount: "件",
    audioSource: "元の音声",
    recordStart: "録音する",
    recordStop: "録音を止める",
    recording: "録音中",
    chooseFile: "ファイルを選ぶ",
    uploading: "取り込んでいます…",
    audioReady: "取り込みました",
    removeAudio: "取り消す",
    recordUnsupported: "このブラウザでは録音できません。ファイルを選んでください。",
    micDenied: "マイクを使えませんでした。ブラウザでマイクの利用を許可してください。",
    micBlockedInFrame: "ControlDeckの中ではマイクを開けません。「ファイルを選ぶ」で音声を渡すか、SonicForgeを直接開いてください。",
    speakerLabel: "組み込みの話者",
    speakerAuto: "言語にあわせる",
    voiceNoteBuiltIn: "保存したボイスを選ぶと、その声で読み上げます。クローンやデザインした声もここに並びます。",
    autoTranscribing: "参照音声を文字起こししています…",
    autoTranscribed: "参照音声を文字起こししました。必要なら直してください。",
    autoTranscribeFailed: "自動の文字起こしはできませんでした。手で入力してください。",
    meetingMinutes: "議事録",
    meetingMakeMinutes: "終わったらLLMで議事録を作る",
    meetingLiveTranslate: "日英の同時翻訳",
    meetingTranslateOn: "同時翻訳: 入",
    meetingTranslateOff: "同時翻訳: 切",
    meetingMinutesPending: "議事録を作っています…",
    chatTitle: "音声で会話する",
    chatHint: "話しかけると、その場で文字にしてControlDeckのAIが答え、声で返します。文字起こしと読み上げのモデルは会話の間ずっと読み込んだままなので、毎回の待ちがありません。",
    chatStart: "会話をはじめる",
    chatStop: "終わる",
    chatTalk: "話しかける",
    chatTalking: "聞いています…（押すと止める）",
    chatThinking: "考えています…",
    chatSpeaking: "返事を読んでいます…",
    chatTurnHint: "話し終えると自動で区切ります。返事のあとまた聞きにいきます。",
    chatConnecting: "つないでいます…",
    chatReady: "どうぞ話してください。",
    chatYou: "あなた",
    chatReply: "AIの返事",
    chatEmpty: "まだ何もありません。",
    chatNeedsHost: "会話はControlDeckのAIを使います。ControlDeckの中から開いてください。",
    chatVoice: "返事の声",
    chatPersona: "AIへの指示",
    chatPersonaDefault: "あなたは話し相手です。相手の話し言葉に、話し言葉で短く答えてください。読み上げるので、箇条書きや記号は使わず、2〜3文にまとめてください。",
    chatPlaybackBlocked: "返事の音を鳴らせませんでした。画面を一度タップしてから、もう一度話しかけてください。",
    segmentWaiting: "聞き取っています…",
    segmentQueued: "順番待ち",
    segmentProgress: "書き起こし中",
    segmentFailed: "失敗",
    playBlocked: "再生するには一度タップしてください",
    hfTokenLabel: "Hugging Face アクセストークン",
    hfTokenHint: "この配布物はHugging Faceの承認が要ります。先にモデルページでライセンスに同意し、同じアカウントのトークンを貼ってください。",
    hfTokenSet: "登録済み",
    hfTokenSave: "保存",
    hfTokenClear: "消す",
    openModelPage: "モデルページを開く",

    needText: "文章を入力してください。",
    needPrompt: "どんな音・曲かを書いてください。",
    needAudio: "先に音声ファイルを選んでください。",
    bridgeOnly: "この操作はControlDeckから開いたときだけ使えます。",
    genericError: "うまくいきませんでした。",
  },
  en: {
    localOnlyHint: "Generation and transcription run only on this machine",
    localOnly: "Local only",
    displayMode: "Display mode",
    modeSimple: "Simple",
    modeAdvanced: "Advanced",
    settings: "Settings",
    settingsTitle: "Runtime and voice settings",
    studio: "Studio",
    library: "Library",
    activity: "Activity",
    pipeline: "Pipeline",

    whatToMake: "What to make",
    taskSpeech: "Speech",
    taskTranscribe: "Transcribe",
    taskSfx: "SFX",
    taskMusic: "Music",
    taskLocalization: "Localization",
    taskMeeting: "Meeting",
    taskChat: "Conversation",
    summarySpeech: "Read your text aloud with the voice you choose.",
    summaryTranscribe: "Turn an audio file into text.",
    summarySfx: "Create a short sound effect from a description.",
    summaryMusic: "Create background music from a description.",
    summaryLocalization: "Render Japanese and English dialogue lines together.",
    summaryMeeting: "Capture what is being said as text, as it happens.",
    summaryChat: "Speak, and the AI answers out loud.",

    speechTextLabel: "Text to read",
    speechStyle: "Delivery",
    contentLanguage: "Language",
    speechLanguageLabel: "Language to read in",
    transcribeLanguageLabel: "Language being spoken",
    voice: "Voice",
    ttsEngine: "Speech engine",
    ttsQwen: "Qwen3-TTS (built-in and designed voices)",
    ttsGptSovits: "GPT-SoVITS (fast, reference-based)",
    ttsEngineSaved: "This choice is saved and used for future TTS calls.",
    gptVoiceRequired: "GPT-SoVITS needs a cloned voice or a model pack with reference audio.",
    builtInVoice: "Built-in voice (recommended)",
    audioFile: "Audio file",
    chooseAudio: "+ Choose an audio file",
    clearFile: "Remove",
    sfxPromptLabel: "What does it sound like?",
    sfxKind: "Kind of sound",
    musicPromptLabel: "What kind of music?",
    musicMood: "Mood",
    length: "Length",
    instrumental: "Instrumental (BGM)",
    create: "Create",
    creating: "Creating…",
    transcribeAction: "Transcribe",
    resetForm: "Reset input and settings",
    refresh: "Refresh",
    filter: "Filter",

    auto: "Auto",
    japanese: "日本語",
    english: "English",
    quality: "Quality",
    qualityFast: "Faster",
    qualityBalanced: "Recommended",
    qualityHigh: "Higher quality",

    styleAuto: "Recommended",
    styleGentle: "Gentle",
    styleBright: "Bright",
    styleCalm: "Calm",
    styleNarration: "Narration",

    sfxUi: "UI",
    sfxImpact: "Impact",
    sfxMechanical: "Mechanical",
    sfxMagic: "Magic / Sci-fi",
    sfxFoley: "Footsteps / Foley",
    sfxAmbience: "Ambience",
    sfxCustom: "No preset",

    moodAuto: "Recommended",
    moodCalm: "Calm",
    moodEnergetic: "Energetic",
    moodTense: "Tense",
    moodEpic: "Epic",
    moodRetro: "Retro",

    bpmSlow: "Slow",
    bpmMedium: "Medium",
    bpmFast: "Fast",
    bpmNone: "Unset",

    advancedCommon: "Shared advanced settings",
    advancedSpeech: "Speech advanced settings",
    advancedTranscribe: "Transcription advanced settings",
    advancedTranscribeHint: "Segments and timings are included as far as the adopted route can report them.",
    advancedSfx: "Sound effect advanced settings",
    advancedMusic: "Music advanced settings",
    advancedRouting: "Engine selection",
    advancedRoutingHint: "Leave blank to let SonicForge pick the most reliable route for this machine.",
    advancedOutputTarget: "Output destination",
    outputFormat: "Output format",
    sampleRate: "Sample rate",
    channels: "Channels",
    profileName: "Profile name",
    engine: "Engine",
    model: "Model",
    modelAuto: "Automatic (recommended)",
    modelKotoba: "Strong in Japanese (kotoba-whisper v2.0)",
    modelWhisperTurbo: "Multilingual (whisper large v3 turbo)",
    modelQwenCustom: "Standard speech (Qwen3-TTS 0.6B)",
    modelQwenDesign: "For designed voices (Qwen3-TTS 1.7B)",
    modelStableAudio: "Sound effects (Stable Audio 3 Small SFX)",
    modelAceStep: "Music (ACE-Step 1.5 Turbo)",
    modelNoteVoice: "With a saved voice selected, the model that voice was built against is used.",
    modelNoteSingle: "This feature currently has a single model.",
    modelNoteMissing: "This feature is not prepared yet. Prepare it from settings.",
    device: "Device",
    seed: "Seed",
    styleInstruction: "Delivery instruction (free text)",
    styleInstructionHint: "Takes precedence over the preset above. Leave blank to use the preset.",
    timestamps: "Show a timestamp for each segment",
    lengthSeconds: "Length (seconds)",
    bpm: "Tempo (BPM)",
    sfxAmbienceHint: "Ambience produces a sustained background instead of a one-shot effect.",
    chooseProjectOutput: "+ Choose a destination",
    projectOutputHint: "The finished audio is also written to the ControlDeck project you choose.",
    projectOutputSelected: "Destination selected.",
    promptPreview: "Description sent",

    preparing: "Preparing",
    running: "Generating",
    queued: "Waiting in queue",
    done: "Ready",
    failed: "Did not finish",
    canceled: "Canceled",
    cancel: "Cancel",
    makeAnother: "Make another",
    exportAsset: "Export",
    details: "Details",
    close: "Close",
    back: "Back",
    save: "Save",
    delete: "Delete",
    recent: "Recent",
    recentEmpty: "Nothing yet. Describe what you want and press Create.",
    noJobs: "No running or finished work yet.",
    libraryEmpty: "No audio yet.",

    exportTitle: "Export audio",
    exportProfile: "Delivery profile",
    filename: "File name",
    exportToProject: "Write into the ControlDeck project",
    exportStarted: "Export started.",

    runtimeTitle: "Available capabilities",
    runtimeHint: "Prepare only what you need, when you need it. Speech Essentials alone covers speech and transcription.",
    setupPlan: "What will be prepared, and hardware",
    setupProfile: "Prepare together",
    setupStart: "Prepare this",
    recheck: "Check again",
    setUp: "Set up",
    repair: "Repair",
    update: "Update",
    openSetup: "Open setup",
    setupRequired: "This capability needs setup first",
    componentGptSovits: "GPT-SoVITS",
    componentGptSovitsDetail: "Fast reference-based speech, installed separately from Qwen3-TTS.",
    profileGptSovits: "GPT-SoVITS only",
    ttsModelsTitle: "GPT-SoVITS models",
    ttsModelsHint: "ZIP files are checked and extracted. The manifest must state rights, license, and source.",
    ttsModelFormat: "manifest.json format inside the ZIP",
    ttsModelUpload: "Add ZIP",
    ttsModelActivate: "Use",
    ttsModelActive: "Active",
    ttsModelDeleteActive: "Switch to another model before deleting the active model.",
    ttsModelDeleteBody: "Delete the model files and management record. This cannot be undone.",
    gptSampleName: "Sample voice name",
    gptSampleLanguage: "Language",
    gptSampleText: "Exact transcript of the audio",
    gptSampleAdd: "Add sample voice",
    gptSampleRequired: "Name, audio, exact transcript, and rights confirmation are required.",
    gptSampleSelect: "Select a registered sample voice",
    gptReference: "Reference sample (voice clone)",
    gptReferenceAdd: "+ Add sample",
    gptReferenceNote: "Inference uses a 3–10 second reference sample or a trained model pack with reference audio. Qwen speaker types do not apply.",
    gptSamplePreset: "Reference sample",
    gptSampleCustom: "My voice (local file)",
    gptSampleLocalHint: "Get the audio from its publisher, then choose that WAV below. SonicForge does not hotlink audio files.",
    gptSampleManagedHint: "Downloads and stores a reference package pinned by publisher, revision, and SHA-256.",
    gptSampleSource: "Source",
    gptSampleTerms: "Terms",
    gptSampleAcceptTerms: "I have reviewed the publisher terms and agree to install and use this sample on this device",
    gptSampleUse: "Select this sample",
    componentCore: "SonicForge core",
    componentSpeech: "Speech Essentials",
    componentSpeechDetail: "Japanese/English speech synthesis and transcription",
    componentGame: "Game Audio",
    componentGameDetail: "Sound effects and ambience (Stable Audio 3 Small-SFX)",
    componentMusic: "Music",
    componentMusicDetail: "Background music and songs (ACE-Step 1.5)",
    profileSpeech: "Speech Essentials only",
    profileGame: "Add Game Audio",
    profileMusic: "Add Music",
    profileFull: "Everything (Full Studio)",
    profileCpu: "CPU-only setup",
    termsStability: "I reviewed and accept the Stability AI Community License",
    termsRequired: "Accept the license first.",
    displayLanguage: "Display language",
    displayLanguageHint: "Follows ControlDeck. Changing it here affects this screen only.",
    backend: "Compute backend",
    freeSpace: "Free space",
    requiredSpace: "Estimated space needed",
    platform: "Platform",
    blockers: "Why it cannot be prepared",
    diagnostics: "Diagnostics",
    capabilityDetail: "Capability states",

    voicesTitle: "Voices",
    voicesHint: "Save a speaker to reuse it. Saved voices appear in the Speech task.",
    voicesEmpty: "Nothing saved yet. The built-in voices work as they are.",
    voiceAdd: "+ Create a voice",
    voiceKind: "How to create it",
    voiceBuiltIn: "Pick a built-in speaker",
    voiceDesign: "Describe the voice in words",
    voiceClone: "Build from reference audio",
    voiceBuiltInHint: "Choose from the shipped speakers. No rights confirmation needed.",
    voiceDesignHint: "Describe the voice you want and SonicForge steers towards it.",
    voiceCloneHint: "Match a voice from your own audio. Requires a rights confirmation.",
    voiceSpeaker: "Speaker",
    voiceInstruction: "Voice description",
    voiceReference: "Reference audio",
    voiceReferenceText: "Reference transcript (optional)",
    voiceLanguages: "Languages",
    voiceRights: "I confirm I have the right to use and clone this voice",
    voiceRightsRequired: "The rights confirmation is required.",
    name: "Name",
    nameRequired: "Enter a name.",
    deleteVoiceTitle: "Delete this voice?",
    deleteVoiceBody: "Audio already generated with it stays, but the voice can no longer be selected.",

    devicesTitle: "Voice agent devices",
    devicesHint: "Pair a small device such as an M5 through ControlDeck. Device firmware is out of scope here.",
    deviceLabel: "Device name",
    deviceRelay: "Relay",
    devicePair: "Create a pairing",

    pipelineTitle: "Audio pipeline",
    pipelineHint: "Chain transcription, the ControlDeck AI, speech, sound effects and music into one run.",
    pipelinePreset: "Common chains",
    pipelineInput: "Input",
    pipelineStages: "Stages",
    pipelineDelivery: "Delivery",
    startAt: "Start at",
    stopAfter: "Stop after",
    deliveryMode: "Form",
    validate: "Check the chain",
    run: "Run",
    fromLibrary: "Pick from the library",
    inputText: "Text",
    inputFile: "Audio file",
    inputAsset: "Library audio",
    stageAsr: "Transcribe",
    stageAi: "ControlDeck AI",
    stageTts: "Speak",
    stageSfx: "Sound effect",
    stageMusic: "Music",
    stageProcess: "Audio processing",
    deliveryText: "Text only",
    deliveryAsset: "Save to library",
    deliveryProject: "Write to a project",
    presetDub: "Transcribe → translate → speak",
    presetTranscribe: "Transcribe only",
    presetSpeak: "Speak only",
    presetRewrite: "Transcribe → summarize",
    presetChat: "Voice chat (speak → AI reply → speak)",
    pipelineValid: "This chain can run",
    pipelineOutputText: "You receive text",
    pipelineOutputAudio: "You receive audio",

    localizationTitle: "Localization Studio",
    localizationHint: "One row per line: ID | character | Japanese | English. Pasted CSV works too.",
    batchName: "Batch name",
    createBatch: "Create batch and render",
    openBatch: "Open an existing batch",
    renderPending: "Render pending",
    renderFailed: "Retry failed",
    renderChanged: "Render changed",
    renderAll: "Render all",
    filenamePattern: "File naming",
    lineId: "ID",
    character: "Character",
    status: "Status",
    locales: "Languages to render",
    noLines: "No rows yet. Fill in the text area above.",

    meetingTitle: "Meeting transcription",
    meetingHint: "Turn microphone audio into text as it happens. Translation and summaries use the ControlDeck AI.",
    meetingStart: "Start recording",
    meetingStop: "Stop and finish",
    meetingRecording: "Recording",
    meetingTitleField: "Meeting name",
    meetingTranslate: "Translate",
    meetingSummarize: "Summarize when finished",
    meetingTargetLanguage: "Translate into",
    meetingChunk: "Segment length (seconds)",
    meetingPast: "Past meetings",
    meetingNoPast: "No recordings yet.",
    meetingTranscript: "Open full transcript",
    meetingMicDenied: "The microphone is not available. Allow microphone access in the browser.",
    meetingMicUnsupported: "This browser cannot record from the microphone.",
    meetingSummary: "Summary",

    stateAvailable: "Available",
    statePreparing: "Preparing",
    stateSetupRequired: "Setup required",
    stateUnavailable: "Unavailable",
    stateFailed: "Failed",
    stateQueued: "Waiting",
    stateRunning: "Running",
    stateSucceeded: "Done",
    stateCanceled: "Canceled",
    provenance: "Generation record",
    audioAsset: "Audio",
    aiInstruction: "Instruction for the AI",
    inputLevel: "Input level",
    itemCount: " items",
    audioSource: "Source audio",
    recordStart: "Record",
    recordStop: "Stop recording",
    recording: "Recording",
    chooseFile: "Choose a file",
    uploading: "Uploading…",
    audioReady: "Ready",
    removeAudio: "Remove",
    recordUnsupported: "This browser cannot record. Choose a file instead.",
    micDenied: "The microphone is not available. Allow microphone access in the browser.",
    micBlockedInFrame: "The microphone cannot be opened inside ControlDeck. Use \"Choose a file\", or open SonicForge directly.",
    speakerLabel: "Built-in speaker",
    speakerAuto: "Match the language",
    voiceNoteBuiltIn: "Pick a saved voice to read with it. Cloned and designed voices appear here too.",
    autoTranscribing: "Transcribing the reference audio…",
    autoTranscribed: "Transcribed the reference audio. Correct it if needed.",
    autoTranscribeFailed: "Could not transcribe automatically. Please type it in.",
    meetingMinutes: "Minutes",
    meetingMakeMinutes: "Write minutes with the LLM when finished",
    meetingLiveTranslate: "Live JA/EN translation",
    meetingTranslateOn: "Translation: on",
    meetingTranslateOff: "Translation: off",
    meetingMinutesPending: "Writing the minutes…",
    chatTitle: "Talk with the AI",
    chatHint: "Speak, and ControlDeck's AI answers out loud. Transcription and speech stay loaded for the whole conversation, so there is no wait between turns.",
    chatStart: "Start talking",
    chatStop: "End",
    chatTalk: "Start talking",
    chatTalking: "Listening… (press to stop)",
    chatThinking: "Thinking…",
    chatSpeaking: "Speaking…",
    chatTurnHint: "It commits when you stop speaking, and listens again after the reply.",
    chatConnecting: "Connecting…",
    chatReady: "Go ahead.",
    chatYou: "You",
    chatReply: "Reply",
    chatEmpty: "Nothing yet.",
    chatNeedsHost: "Conversation uses ControlDeck's AI. Open this from inside ControlDeck.",
    chatVoice: "Reply voice",
    chatPersona: "Instruction for the AI",
    chatPersonaDefault: "You are a conversation partner. Answer spoken language with spoken language, briefly. It will be read aloud, so no bullets or symbols -- two or three sentences.",
    chatPlaybackBlocked: "The reply could not be played. Tap the screen once, then speak again.",
    segmentWaiting: "Listening…",
    segmentQueued: "Queued",
    segmentProgress: "Transcribing",
    segmentFailed: "Failed",
    playBlocked: "Tap once to allow playback",
    hfTokenLabel: "Hugging Face access token",
    hfTokenHint: "This model is gated on Hugging Face. Accept its license on the model page first, then paste an access token from that same account.",
    hfTokenSet: "Saved",
    hfTokenSave: "Save",
    hfTokenClear: "Clear",
    openModelPage: "Open the model page",

    needText: "Enter some text.",
    needPrompt: "Describe the sound or music you want.",
    needAudio: "Choose an audio file first.",
    bridgeOnly: "This action is only available when opened from ControlDeck.",
    genericError: "That did not work.",
  },
};

const TASKS = ["speech", "transcribe", "sfx", "music", "localization", "meeting", "chat"];
const ADVANCED_TASKS = new Set(["localization"]);
const VIEWS = ["studio", "library", "activity", "pipeline", "settings"];
const ACTIVE_STATES = new Set(["queued", "running"]);

/* 音の種類ごとの既定。descriptor は利用者が書いた説明の言語に合わせて足す。
   英語のみを受け付けるエンジンには、サーバ側の正規化が日本語を訳して渡す。 */
const SFX_KINDS = [
  {id: "ui", label: "sfxUi", task: "audio.sfx.generate", seconds: 1,
   ja: "短く清潔なユーザーインターフェース操作音", en: "short clean user interface sound"},
  {id: "impact", label: "sfxImpact", task: "audio.sfx.generate", seconds: 2,
   ja: "力強い打撃音、立ち上がりが速く余韻が短い", en: "strong impact hit with a fast attack and short tail"},
  {id: "mechanical", label: "sfxMechanical", task: "audio.sfx.generate", seconds: 3,
   ja: "機械的な動作音、金属とモーターの質感", en: "mechanical actuation with metal and motor texture"},
  {id: "magic", label: "sfxMagic", task: "audio.sfx.generate", seconds: 3,
   ja: "魔法・SF的な効果音、きらめきと唸り", en: "magical sci-fi effect with shimmer and drone"},
  {id: "foley", label: "sfxFoley", task: "audio.sfx.generate", seconds: 2,
   ja: "生活音・足音のような現実的なフォーリー", en: "realistic foley such as footsteps and handling"},
  {id: "ambience", label: "sfxAmbience", task: "audio.ambience.generate", seconds: 10,
   ja: "途切れず続く環境音、背景として自然に馴染む", en: "continuous background ambience that loops naturally"},
  {id: "custom", label: "sfxCustom", task: "audio.sfx.generate", seconds: 3, ja: "", en: ""},
];

const MUSIC_MOODS = [
  {id: "auto", label: "moodAuto", ja: "", en: ""},
  {id: "calm", label: "moodCalm", ja: "静かで落ち着いた雰囲気", en: "calm and quiet mood"},
  {id: "energetic", label: "moodEnergetic", ja: "明るく元気で前向きな雰囲気", en: "bright energetic upbeat mood"},
  {id: "tense", label: "moodTense", ja: "緊張感のある張り詰めた雰囲気", en: "tense suspenseful mood"},
  {id: "epic", label: "moodEpic", ja: "壮大で厚みのある雰囲気", en: "epic cinematic mood"},
  {id: "retro", label: "moodRetro", ja: "レトロなチップチューン風", en: "retro chiptune style"},
];

const SPEECH_STYLES = [
  {id: "auto", label: "styleAuto", instruction: ""},
  {id: "gentle", label: "styleGentle", instruction: "Speak gently and warmly at a calm, unhurried pace."},
  {id: "bright", label: "styleBright", instruction: "Speak brightly and energetically, with a lively rhythm."},
  {id: "calm", label: "styleCalm", instruction: "Speak calmly and quietly, with a low and steady tone."},
  {id: "narration", label: "styleNarration", instruction: "Read as a clear, neutral narration with even pacing."},
];

const LANGUAGES = [
  {id: "auto", label: "auto"},
  {id: "ja", label: "japanese"},
  {id: "en", label: "english"},
];

const QUALITIES = [
  {id: "fast", label: "qualityFast"},
  {id: "balanced", label: "qualityBalanced"},
  {id: "quality", label: "qualityHigh"},
];

const SETUP_COMPONENTS = [
  {id: "core", label: "componentCore", detail: null, profile: null},
  {id: "speech-essentials", label: "componentSpeech", detail: "componentSpeechDetail", profile: "speech-essentials"},
  {id: "gpt-sovits", label: "componentGptSovits", detail: "componentGptSovitsDetail", profile: "gpt-sovits"},
  {id: "game-audio", label: "componentGame", detail: "componentGameDetail", profile: "game-audio"},
  {id: "music", label: "componentMusic", detail: "componentMusicDetail", profile: "music"},
];

const SETUP_PROFILES = [
  {id: "speech-essentials", label: "profileSpeech"},
  {id: "gpt-sovits", label: "profileGptSovits"},
  {id: "game-audio", label: "profileGame"},
  {id: "music", label: "profileMusic"},
  {id: "full-studio", label: "profileFull"},
  {id: "cpu-essentials", label: "profileCpu"},
];

const MODEL_LABELS = {
  "kotoba-tech/kotoba-whisper-v2.0": "modelKotoba",
  "openai/whisper-large-v3-turbo": "modelWhisperTurbo",
  "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice": "modelQwenCustom",
  "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign": "modelQwenDesign",
  "lj1995/GPT-SoVITS": "GPT-SoVITS v2 ProPlus",
  "stabilityai/stable-audio-3-small-sfx": "modelStableAudio",
  "acestep-v15-turbo": "modelAceStep",
};

const TASK_CAPABILITY = {
  speech: "speech.tts.synthesize",
  transcribe: "speech.asr.transcribe",
  sfx: "audio.sfx.generate",
  music: "music.generate",
  localization: "speech.localization.batch",
  meeting: "speech.asr.transcribe",
  chat: "speech.asr.transcribe",
};

const CAPABILITY_COMPONENT = {
  "speech.tts.synthesize": "speech-essentials",
  "speech.asr.transcribe": "speech-essentials",
  "speech.localization.batch": "speech-essentials",
  "audio.sfx.generate": "game-audio",
  "audio.ambience.generate": "game-audio",
  "music.generate": "music",
};

const PIPELINE_STAGE_LABEL = {
  "speech.asr": "stageAsr",
  "host.ai.text": "stageAi",
  "speech.tts": "stageTts",
  "audio.sfx": "stageSfx",
  "music.generate": "stageMusic",
  "audio.process": "stageProcess",
};

const PIPELINE_PRESETS = [
  {id: "dub", label: "presetDub", input: "audio_upload", delivery: "asset",
   stages: [{id: "asr", kind: "speech.asr"}, {id: "translate", kind: "host.ai.text"}, {id: "tts", kind: "speech.tts"}]},
  {id: "transcribe", label: "presetTranscribe", input: "audio_upload", delivery: "text",
   stages: [{id: "asr", kind: "speech.asr"}]},
  {id: "speak", label: "presetSpeak", input: "text", delivery: "asset",
   stages: [{id: "tts", kind: "speech.tts"}]},
  {id: "summary", label: "presetRewrite", input: "audio_upload", delivery: "text",
   stages: [{id: "asr", kind: "speech.asr"}, {id: "summarize", kind: "host.ai.text"}]},
  /* 音声チャット。話しかけて、返事を声で受け取る 1 往復。指示を空にしないのは、
     既定のままでも会話として成り立つようにするため。 */
  {id: "chat", label: "presetChat", input: "audio_upload", delivery: "asset",
   stages: [
     {id: "asr", kind: "speech.asr"},
     {id: "reply", kind: "host.ai.text",
      instruction: "あなたは話し相手です。相手の話し言葉に、話し言葉で短く答えてください。読み上げるので、箇条書きや記号は使わず、2〜3文にまとめてください。"},
     {id: "tts", kind: "speech.tts"},
   ]},
];

/* ── 状態 ─────────────────────────────────────────────────────────────── */

const state = {
  locale: (navigator.language || "ja").startsWith("en") ? "en" : "ja",
  localeFromHost: false,
  mode: "simple",
  view: "studio",
  task: "speech",
  lastNonSettingsView: "studio",
  socket: null,
  reconnectTimer: 0,
  reconnectAttempt: 0,
  bridgePort: null,
  nonce: "",
  hostBusy: false,
  sequence: 0,
  activeJob: "",
  jobs: [],
  assets: [],
  voices: [],
  capabilities: null,
  models: null,
  ttsPreferences: null,
  ttsModels: [],
  ttsSamples: [],
  setup: null,
  plan: null,
  deliveryProfiles: [],
  credentials: null,
  libraryFilter: "all",
  exportAssetId: "",
  confirmAction: null,
  /* 入力の持ち物。再描画で消えないようにここに置く。 */
  form: {},
  /* 文字起こしとクローン参照音声の入れ物。録音とファイル選択の両方がここに入る。 */
  transcribeAudio: null,
  voiceReference: null,
  projectGrant: "",
  voiceKind: "built-in",
  voiceLanguages: ["ja", "en"],
  pipeline: null,
  meeting: null,
};

const byId = (id) => document.getElementById(id);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const t = (key) => I18N[state.locale][key] ?? I18N.ja[key] ?? key;
const app = () => byId("app");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (c) =>
    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}[c]));
}

/* サーバの失敗は機械向けのコードで来ることがある（terms_required:<id> など）。
   そのまま出すと利用者には読めないので、分かる分だけ言葉に置き換える。 */
function jobFailureText(job) {
  const raw = String(job.error_message || "").trim();
  if (!raw) return t("failed");
  if (raw.startsWith("terms_required")) return t("termsRequired");
  if (job.error_code === "worker_failed" && !likelyJapanese(raw) && !/\s/.test(raw)) return t("failed");
  return raw;
}

function errorText(error) {
  if (typeof error === "string") return error;
  return error?.message || error?.detail || error?.code || t("genericError");
}

const JAPANESE_RE = /[぀-ヿ㐀-鿿]/;
function likelyJapanese(value) { return JAPANESE_RE.test(String(value || "")); }

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes <= 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let index = 0;
  let size = bytes;
  while (size >= 1024 && index < units.length - 1) { size /= 1024; index += 1; }
  return `${size >= 10 || index === 0 ? Math.round(size) : size.toFixed(1)} ${units[index]}`;
}

function formatSeconds(ms) {
  const total = Math.round(Number(ms || 0) / 1000);
  if (!Number.isFinite(total) || total <= 0) return "—";
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return minutes > 0 ? `${minutes}:${String(seconds).padStart(2, "0")}` : `${seconds}s`;
}

function formatClock(ms) {
  const total = Math.floor(Number(ms || 0) / 1000);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

/* ── テーマとセーフエリア ─────────────────────────────────────────────── */

function applyTheme(theme = {}) {
  const root = document.documentElement;
  for (const name of ["bg", "surface", "text", "border", "muted", "accent"]) {
    if (typeof theme[name] === "string") root.style.setProperty(`--${name}`, theme[name]);
  }
  if (typeof theme.surface === "string") root.style.setProperty("--sunk", theme.bg || theme.surface);
  if (theme.color_scheme) {
    root.style.colorScheme = theme.color_scheme;
    root.style.setProperty("--accent-ink", theme.color_scheme === "dark" ? "#10131f" : "#ffffff");
  }
  if (typeof theme.radius_md === "number") root.style.setProperty("--radius", `${theme.radius_md}px`);
  if (theme.safe_area) applySafeArea(theme.safe_area);
  if (theme.locale === "ja" || theme.locale === "en") {
    state.localeFromHost = true;
    state.locale = theme.locale;
    applyLocale();
  }
}

function applySafeArea(value = {}) {
  for (const side of ["top", "right", "bottom", "left"]) {
    if (Number.isFinite(value[side])) {
      document.documentElement.style.setProperty(`--safe-${side}`, `${value[side]}px`);
    }
  }
}

/* ── ホストブリッジ ───────────────────────────────────────────────────── */

function callHost(method, params = {}) {
  if (!state.bridgePort) return Promise.reject({code: "bridge_unavailable"});
  return new Promise((resolve, reject) => {
    const id = `sonic-forge-host-${++state.sequence}`;
    const listener = (event) => {
      const message = event.data;
      if (message?.type !== "response" || message.id !== id) return;
      state.bridgePort.removeEventListener("message", listener);
      message.ok ? resolve(message.result) : reject(message.error);
    };
    state.bridgePort.addEventListener("message", listener);
    state.bridgePort.postMessage({id, method, params, session_nonce: state.nonce});
  });
}

/* 実行中の仕事はサーバ側の durable job として残るので、入力しただけでは
   「未保存」を立てない。失うものがあるのは受付の最中だけである。 */
function setHostBusy(value) {
  if (state.hostBusy === value) return;
  state.hostBusy = value;
  if (!state.bridgePort) return;
  void callHost("host.busy.set", {busy: value}).catch(() => { state.hostBusy = !value; });
}

window.addEventListener("message", (event) => {
  let expected = location.origin;
  try { if (document.referrer) expected = new URL(document.referrer).origin; } catch { /* 単体表示 */ }
  if (event.source !== parent || event.origin !== expected) return;
  if (event.data?.type !== "control-deck-host.connected" || !event.ports[0]) return;
  state.bridgePort = event.ports[0];
  state.nonce = event.data.session_nonce;
  document.documentElement.dataset.bridge = "ready";
  app().setAttribute("aria-busy", "false");
  applyTheme(event.data.theme || {});
  state.bridgePort.onmessage = (message) => {
    const value = message.data;
    if (value?.type !== "event") return;
    if (value.event === "locale.changed" && (value.data?.locale === "ja" || value.data?.locale === "en")) {
      state.localeFromHost = true;
      state.locale = value.data.locale;
      applyLocale();
    }
    if (value.event === "audio.frame") receiveHostAudioFrame(value.data);
    if (value.event === "theme.changed") applyTheme(value.data || {});
    if (value.event === "safe_area.changed") applySafeArea(value.data || {});
    if (value.event === "session.updated" && typeof value.data?.session_nonce === "string") {
      state.nonce = value.data.session_nonce;
      state.socket?.close();
    }
    if (value.event === "visibility.changed" && value.data?.visible) {
      connect();
      void reloadAuthoritative();
    }
  };
  state.bridgePort.start?.();
  void callHost("host.title.set", {title: "SonicForge"}).catch(() => {});
  connect();
  void reloadAuthoritative();
});

if (parent !== window) {
  parent.postMessage({type: "control-deck-addon.connect", bridge_version: "1.0"}, "*");
} else {
  document.documentElement.dataset.bridge = "standalone";
}

/* ── 転送 ─────────────────────────────────────────────────────────────── */

const proxyRoot = location.pathname.startsWith("/addon-frame/")
  ? "/" + location.pathname.split("/").filter(Boolean).slice(0, 2).join("/")
  : "";
const API = `${proxyRoot}/addon/v1`;
const apiUrl = (path) => `${API}${path}`;

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (proxyRoot && state.nonce) headers.set("X-Control-Deck-Bridge-Session", state.nonce);
  const request = {...options, headers};
  if (proxyRoot) request.credentials = 'include';
  const response = await fetch(apiUrl(path), request);
  const text = await response.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = {detail: text}; }
  if (!response.ok) throw data.detail || data.error || {message: `HTTP ${response.status}`};
  return data;
}

const jsonPost = (path, body) => api(path, {
  method: "POST",
  headers: {"content-type": "application/json"},
  body: JSON.stringify(body),
});

function socketOpen() { return state.socket && state.socket.readyState === WebSocket.OPEN; }

function scheduleReconnect() {
  clearTimeout(state.reconnectTimer);
  if (document.hidden) return;
  const delay = Math.min(30000, 1000 * 2 ** Math.min(state.reconnectAttempt++, 5));
  state.reconnectTimer = setTimeout(connect, delay);
}

function connect() {
  if (state.socket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(state.socket.readyState)) return;
  if (proxyRoot && !state.nonce) return;
  clearTimeout(state.reconnectTimer);
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}${API}/events`;
  state.socket = proxyRoot ? new WebSocket(url, [`control-deck-bridge.${state.nonce}`]) : new WebSocket(url);
  state.socket.onopen = () => { state.reconnectAttempt = 0; void reloadAuthoritative(); };
  state.socket.onmessage = (event) => {
    let value;
    try { value = JSON.parse(event.data); } catch { return; }
    if (value.type === "job" && value.job_id) {
      if (!state.activeJob || state.activeJob === value.job_id) {
        state.activeJob = value.job_id;
        void showJob(value.job_id);
      } else {
        void loadActiveJobs();
      }
    }
    if (value.type === "setup") {
      void loadSetup();
      void loadCapabilities();
      if (value.job_id) void showJob(value.job_id);
    }
  };
  state.socket.onerror = () => {};
  state.socket.onclose = () => { state.socket = null; scheduleReconnect(); };
}

/* ── ロケール・モード・画面 ───────────────────────────────────────────── */

/* <label>言語<select>…</select></label> のように、見出しの文言と操作が同じ要素に
   入っていることがある。textContent を丸ごと差し替えると中の select ごと消える
   （実機でボイス欄が空欄になっていた原因）。文言のところだけ差し替える。 */
function setLocalizedText(node, value) {
  if (!node.children.length) { node.textContent = value; return; }
  const first = node.firstChild;
  if (first && first.nodeType === Node.TEXT_NODE) { first.nodeValue = value; return; }
  node.insertBefore(document.createTextNode(value), first);
}

function applyLocale() {
  document.documentElement.lang = state.locale;
  for (const node of $$("[data-i18n]")) setLocalizedText(node, t(node.dataset.i18n));
  for (const node of $$("[data-i18n-label]")) node.setAttribute("aria-label", t(node.dataset.i18nLabel));
  for (const node of $$("[data-i18n-title]")) node.setAttribute("title", t(node.dataset.i18nTitle));
  renderServicePill();
  renderTaskChoices();
  byId("task-summary").textContent = t(`summary${state.task[0].toUpperCase()}${state.task.slice(1)}`);
  /* 出しっぱなしの結果カードは、言語を変えても前の言語のまま残っていた。
     直前のジョブを持っておいて、ここで描き直す。 */
  if (state.lastJob) renderJobStage(state.lastJob);
  mountAdvanced();
  renderStudio();
  renderLibrary();
  renderRecent();
  renderActivity();
  renderSettings();
  renderPipeline();
  window.renderLocalizationStudio?.();
  renderMeetingPanel();
}

function setMode(mode, {persist = true} = {}) {
  state.mode = mode === "advanced" ? "advanced" : "simple";
  app().dataset.mode = state.mode;
  byId("mode-simple").setAttribute("aria-pressed", String(state.mode === "simple"));
  byId("mode-advanced").setAttribute("aria-pressed", String(state.mode === "advanced"));
  for (const node of $$("[data-advanced-only]")) node.hidden = state.mode !== "advanced";
  /* シンプルへ戻したときに、詳細だけの画面へ取り残されないようにする。 */
  if (state.mode !== "advanced" && ADVANCED_TASKS.has(state.task)) setTask("speech");
  /* 詳細だけの作るもの（ローカライズ・会議）は、モードを変えた時点で
     選択肢に出入りする。ここで描き直さないと、詳細にしても選べない。 */
  renderTaskChoices();
  mountAdvanced();
  renderStudio();
  renderSettings();
  if (persist) remember("mode", state.mode);
}

/* 表示の好みだけを覚える。ここが読めない環境（プライベート窓など）でも、
   既定のシンプルで問題なく使えるようにしておく。 */
function remember(key, value) {
  try { localStorage.setItem(`sonicforge.${key}`, value); } catch { /* 保存できなくても操作は続く */ }
}
function recall(key) {
  try { return localStorage.getItem(`sonicforge.${key}`); } catch { return null; }
}

function activate(name, {sync = true} = {}) {
  const view = VIEWS.includes(name) ? name : "studio";
  if (state.view && state.view !== "settings") state.lastNonSettingsView = state.view;
  state.view = view;
  app().dataset.view = view;
  for (const section of $$(".view")) section.hidden = section.dataset.view !== view;
  for (const button of $$("#shell-nav button")) {
    button.setAttribute("aria-current", button.dataset.view === view ? "page" : "false");
  }
  byId("nav-settings").setAttribute("aria-current", view === "settings" ? "page" : "false");
  if (view === "library") void loadAssets();
  if (view === "activity") void loadActiveJobs();
  if (view === "settings") {
    void loadSetup(); void loadVoices(); void loadPlan(); void loadCredentials(); void loadTtsSettings();
  }
  if (view === "pipeline") renderPipeline();
  if (sync && state.bridgePort) {
    void callHost("host.route.sync", {path: view === "studio" ? "/" : `/${view}`}).catch(() => {});
  }
  window.scrollTo({top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
}

function setTask(task) {
  state.task = TASKS.includes(task) ? task : "speech";
  app().dataset.task = state.task;
  renderTaskChoices();
  byId("task-summary").textContent = t(`summary${state.task[0].toUpperCase()}${state.task.slice(1)}`);
  byId("localization-panel").hidden = state.task !== "localization";
  byId("meeting-panel").hidden = state.task !== "meeting";
  byId("chat-panel").hidden = state.task !== "chat";
  if (state.task === "chat") renderChatPanel();
  for (const node of $$("[data-task-fields]")) node.hidden = node.dataset.taskFields !== state.task;
  mountAdvanced();
  renderStudio();
  if (state.task === "localization") window.renderLocalizationStudio?.();
  if (state.task === "meeting") { renderMeetingPanel(); void loadMeetings(); }
  remember("task", state.task);
}

/* 詳細モードの断片は hidden にせず DOM から外す。タブ順とスクリーンリーダーを
   汚さないため、そして「見えているのに効かない欄」を作らないため。 */
function mountAdvanced() {
  for (const slot of $$("[data-adv-slot]")) {
    slot.replaceChildren();
    if (state.mode !== "advanced") continue;
    if (ADVANCED_TASKS.has(state.task)) continue;
    const name = slot.dataset.advSlot === "task" ? `task-${state.task}` : slot.dataset.advSlot;
    const template = document.querySelector(`[data-adv-template="${name}"]`);
    if (template) slot.append(template.content.cloneNode(true));
  }
  if (state.mode !== "advanced") return;
  syncAdvanced();
}

function syncAdvanced() {
  const quality = byId("advanced-quality");
  if (quality) {
    quality.replaceChildren(...QUALITIES.map((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = t(item.label);
      return option;
    }));
    quality.value = state.form.quality || "balanced";
    quality.onchange = () => { state.form.quality = quality.value; };
  }
  bindAdvancedValue("advanced-format", "format", "wav");
  bindAdvancedValue("advanced-sample-rate", "sampleRate", "");
  bindAdvancedValue("advanced-channels", "channels", "");
  bindAdvancedValue("advanced-profile", "profile", "");
  renderRoutingChoices();
  bindAdvancedValue("advanced-device", "device", "auto");
  bindAdvancedValue("advanced-seed", "seed", "");
  bindAdvancedValue("advanced-style-instruction", "styleInstruction", "");
  bindAdvancedValue("advanced-speaker", "speaker", "");
  bindAdvancedValue("advanced-bpm", "bpm", "");
  const timestamps = byId("advanced-timestamps");
  if (timestamps) {
    timestamps.checked = state.form.timestamps !== false;
    timestamps.onchange = () => { state.form.timestamps = timestamps.checked; };
  }
  const duration = byId("advanced-duration");
  if (duration) {
    duration.value = String(currentDuration());
    duration.onchange = () => {
      state.form[state.task === "music" ? "musicSeconds" : "sfxSeconds"] = Number(duration.value);
      renderStudio();
    };
  }
  const bpmChips = byId("advanced-bpm-chips");
  if (bpmChips) {
    renderChips(bpmChips, [
      {id: "", label: "bpmNone"}, {id: "80", label: "bpmSlow"},
      {id: "110", label: "bpmMedium"}, {id: "140", label: "bpmFast"},
    ], String(state.form.bpm ?? ""), (value) => {
      state.form.bpm = value;
      const input = byId("advanced-bpm");
      if (input) input.value = value;
      syncAdvanced();
    });
  }
  const projectPick = byId("advanced-project-pick");
  if (projectPick) {
    projectPick.classList.toggle("filled", Boolean(state.projectGrant));
    projectPick.textContent = state.projectGrant ? t("projectOutputSelected") : t("chooseProjectOutput");
    projectPick.onclick = pickProjectOutput;
    const clear = byId("advanced-project-clear");
    if (clear) {
      clear.hidden = !state.projectGrant;
      clear.onclick = () => { state.projectGrant = ""; syncAdvanced(); };
    }
  }
}

function bindAdvancedValue(id, key, fallback) {
  const node = byId(id);
  if (!node) return;
  node.value = state.form[key] ?? fallback;
  const handler = () => { state.form[key] = node.value; };
  node.onchange = handler;
  node.oninput = handler;
}

/* ── 選択肢の描画 ─────────────────────────────────────────────────────── */

function renderChips(container, items, selected, onSelect, {multi = false} = {}) {
  if (!container) return;
  container.replaceChildren(...items.map((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.textContent = item.text ?? t(item.label);
    const active = multi ? selected.includes(item.id) : selected === item.id;
    button.setAttribute(multi ? "aria-pressed" : "aria-checked", String(active));
    if (!multi) button.setAttribute("role", "radio");
    if (item.disabled) button.disabled = true;
    button.onclick = () => onSelect(item.id, item);
    return button;
  }));
}

/* 作るものの一覧は、モードによって数が変わる。帯にすると幅が伸び縮みして
   ヘッダの他の操作を押し出すので、幅の変わらない 1 つのつまみに畳んでいる。 */
function taskChoices() {
  return TASKS.filter((task) => state.mode === "advanced" || !ADVANCED_TASKS.has(task));
}

function taskLabel(task) {
  return t(`task${task[0].toUpperCase()}${task.slice(1)}`);
}

/* エンジンとモデルは、いまの作るものに紐づく。自由入力だと利用者は
   Hugging Face のリポジトリ名を暗記していないと選べないので、名前で並べる。 */
function taskModels() {
  const capability = TASK_CAPABILITY[state.task];
  return (state.models?.tasks || []).find((item) => item.task === capability) || null;
}

function renderRoutingChoices() {
  const engine = byId("advanced-engine");
  const model = byId("advanced-model");
  const note = byId("advanced-model-note");
  if (!engine || !model) return;
  const entry = taskModels();
  const options = (values) => values.map((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.text;
    return option;
  });

  const engines = entry?.engines || (entry ? [{id: entry.engine, installed: entry.installed, models: entry.models}] : []);
  engine.replaceChildren(...options([
    {value: "", text: t("modelAuto")},
    ...engines.map((item) => ({
      value: item.id,
      text: `${item.id}${item.installed ? "" : ` — ${t("modelNoteMissing")}`}`,
    })),
  ]));
  const requestedEngine = state.task === "speech"
    ? (state.ttsPreferences?.engine_id || "tts.qwen3")
    : (state.form.engine || "");
  engine.value = requestedEngine;
  if (engine.value !== requestedEngine) engine.value = "";
  engine.onchange = () => {
    if (state.task === "speech" && engine.value) {
      void saveTtsPreference(engine.value).catch((error) => showError("studio-error", errorText(error)));
    } else {
      state.form.engine = engine.value;
    }
    state.form.model = "";
    renderRoutingChoices();
  };

  const selectedEngine = engines.find((item) => item.id === requestedEngine);
  const models = selectedEngine?.models || entry?.models || [];

  model.replaceChildren(...options([
    {value: "", text: t("modelAuto")},
    ...models.map((item) => ({value: item.id, text: t(MODEL_LABELS[item.id]) || item.id})),
  ]));
  const requestedModel = state.task === "speech" && requestedEngine === "tts.gpt-sovits"
    ? (state.ttsPreferences?.gpt_sovits_model_id || "lj1995/GPT-SoVITS")
    : (state.form.model || "");
  model.value = requestedModel;
  if (model.value !== requestedModel) model.value = "";
  model.onchange = () => {
    if (state.task === "speech" && requestedEngine === "tts.gpt-sovits" && model.value) {
      void saveTtsPreference(requestedEngine, model.value)
        .catch((error) => showError("studio-error", errorText(error)));
    } else {
      state.form.model = model.value;
    }
  };

  if (note) {
    note.textContent = !entry ? ""
      : !entry.installed ? t("modelNoteMissing")
      : state.task === "speech" && state.form.voiceId ? t("modelNoteVoice")
      : models.length < 2 ? t("modelNoteSingle")
      : "";
    note.hidden = !note.textContent;
  }
}

/* 作るものは絵で示す。名前を全部並べると 1 行に収まらないうえ、いま何を
   作っているかは下の 1 行の説明と、選んだときの一覧が受け持てる。 */
const TASK_ICONS = {
  speech: ["M12 4.5v9", "M8.5 7v4", "M15.5 7v4", "M5 9v1", "M19 9v1", "M7 18h10"],
  transcribe: ["M6 3.6h8.4L18.4 7.6V20.4H6z", "M14 3.8v4h4", "M8.6 12h6.8", "M8.6 15.4h6.8", "M8.6 18h4.2"],
  sfx: ["M12 3.6v3.2", "M12 17.2v3.2", "M4.4 12h3.2", "M16.4 12h3.2", "M6.6 6.6l2.3 2.3", "M15.1 15.1l2.3 2.3", "M17.4 6.6l-2.3 2.3", "M8.9 15.1l-2.3 2.3"],
  music: ["M9.4 17.6V5.6l9.2-1.8v12", "M9.4 17.6a2.6 2.6 0 1 1-5.2 0 2.6 2.6 0 0 1 5.2 0Z", "M18.6 15.8a2.6 2.6 0 1 1-5.2 0 2.6 2.6 0 0 1 5.2 0Z"],
  localization: ["M12 3.6a8.4 8.4 0 1 0 0 16.8 8.4 8.4 0 0 0 0-16.8Z", "M3.6 12h16.8", "M12 3.6c2.2 2.4 3.3 5.3 3.3 8.4S14.2 18 12 20.4c-2.2-2.4-3.3-5.3-3.3-8.4S9.8 6 12 3.6Z"],
  meeting: ["M9 10.4a2.6 2.6 0 1 0 0-5.2 2.6 2.6 0 0 0 0 5.2Z", "M3.6 19.4c0-3 2.4-5.4 5.4-5.4s5.4 2.4 5.4 5.4", "M16.2 6.2a2.4 2.4 0 0 1 0 4.6", "M17.4 14.4c1.8.7 3 2.4 3 4.4"],
  chat: ["M4.2 5.6h11.2v7.6H8.6l-4.4 3.4z", "M10.6 9.4h.01", "M13 9.4h.01", "M8.2 9.4h.01", "M19.8 9.2v9.6l-3-2.4h-4.6"],
};

function renderTaskChoices() {
  const select = byId("task-select");
  select.replaceChildren(...taskChoices().map((task) => {
    const option = document.createElement("option");
    option.value = task;
    option.textContent = taskLabel(task);
    return option;
  }));
  select.value = state.task;
  const icon = byId("task-icon");
  if (icon) {
    icon.replaceChildren(...(TASK_ICONS[state.task] || []).map((d) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", d);
      return path;
    }));
  }
  /* 絵だけでは何の機能か分からないことがある。押す前に名前を読めるようにする。 */
  const wrapper = byId("task-switch");
  if (wrapper) wrapper.title = `${t("whatToMake")}: ${taskLabel(state.task)}`;
}

function currentSfxKind() {
  return SFX_KINDS.find((item) => item.id === (state.form.sfxKind || "custom")) || SFX_KINDS[6];
}

function currentDuration() {
  if (state.task === "music") return Number(state.form.musicSeconds ?? 30);
  return Number(state.form.sfxSeconds ?? currentSfxKind().seconds);
}

/* 種類・雰囲気の指定は、利用者が書いた説明と同じ言語で足す。訳しながら足すと
   サーバ側の正規化が二重にかかって、意図が薄まる。 */
function composedPrompt() {
  const base = state.task === "music"
    ? String(byId("music-prompt")?.value || "").trim()
    : String(byId("sfx-prompt")?.value || "").trim();
  const source = state.task === "music"
    ? MUSIC_MOODS.find((item) => item.id === (state.form.musicMood || "auto"))
    : currentSfxKind();
  const descriptor = likelyJapanese(base) ? source?.ja : source?.en;
  if (!base || !descriptor) return base;
  return likelyJapanese(base) ? `${base}。${descriptor}` : `${base}, ${descriptor}`;
}

function renderStudio() {
  if (ADVANCED_TASKS.has(state.task)) {
    byId("studio-submit").hidden = true;
    return;
  }
  byId("studio-submit").hidden = false;
  renderChips(byId("speech-style-chips"), SPEECH_STYLES, state.form.speechStyle || "auto", (value) => {
    state.form.speechStyle = value;
    renderStudio();
  });
  renderChips(byId("speech-language-chips"), LANGUAGES, state.form.speechLanguage || "auto", (value) => {
    state.form.speechLanguage = value;
    renderStudio();
  });
  renderChips(byId("transcribe-language-chips"), LANGUAGES, state.form.transcribeLanguage || "auto", (value) => {
    state.form.transcribeLanguage = value;
    renderStudio();
  });
  renderChips(byId("sfx-kind-chips"), SFX_KINDS, state.form.sfxKind || "custom", (value, item) => {
    state.form.sfxKind = value;
    state.form.sfxSeconds = item.seconds;
    renderStudio();
    syncAdvanced();
  });
  renderChips(byId("sfx-length-chips"), [1, 2, 3, 5, 10].map((s) => ({id: s, text: `${s}s`})),
    Number(state.form.sfxSeconds ?? currentSfxKind().seconds), (value) => {
      state.form.sfxSeconds = value;
      renderStudio();
      syncAdvanced();
    });
  renderChips(byId("music-mood-chips"), MUSIC_MOODS, state.form.musicMood || "auto", (value) => {
    state.form.musicMood = value;
    renderStudio();
  });
  renderChips(byId("music-length-chips"), [15, 30, 60, 120].map((s) => ({id: s, text: `${s}s`})),
    Number(state.form.musicSeconds ?? 30), (value) => {
      state.form.musicSeconds = value;
      renderStudio();
      syncAdvanced();
    });

  const speechEngine = byId("speech-engine");
  const selectedTtsEngine = state.ttsPreferences?.engine_id || "tts.qwen3";
  const gptSelected = selectedTtsEngine === "tts.gpt-sovits";
  const engineChoices = [
    {id: "tts.qwen3", label: "ttsQwen"},
    {id: "tts.gpt-sovits", label: "ttsGptSovits"},
  ];
  speechEngine.replaceChildren(...engineChoices.map((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    const catalogEngine = taskModels()?.engines?.find((entry) => entry.id === item.id);
    const missing = item.id === "tts.gpt-sovits" && catalogEngine?.installed === false;
    option.textContent = `${t(item.label)}${missing ? ` — ${t("modelNoteMissing")}` : ""}`;
    option.disabled = missing && selectedTtsEngine !== item.id;
    return option;
  }));
  speechEngine.value = selectedTtsEngine;
  speechEngine.onchange = () => {
    void saveTtsPreference(speechEngine.value)
      .catch((error) => showError("studio-error", errorText(error)));
  };
  byId("speech-engine-note").textContent = t("ttsEngineSaved");

  const voice = byId("speech-voice");
  const selected = voice.value || state.form.voiceId || (gptSelected ? state.ttsPreferences?.gpt_sovits_voice_id : "") || "";
  const speechVoices = gptSelected
    ? state.voices.filter((item) => item.source_type === "clone" && (!item.engine_id || item.engine_id === "tts.gpt-sovits"))
    : state.voices.filter((item) => item.engine_id !== "tts.gpt-sovits");
  voice.replaceChildren(...[{id: "", name: gptSelected ? t("gptSampleSelect") : t("builtInVoice")}, ...speechVoices.map((item) => ({
    id: item.id,
    name: `${item.name} · ${(item.languages || []).join("/")}`,
  }))].map((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.name;
    return option;
  }));
  voice.value = selected;
  if (voice.value !== selected) state.form.voiceId = "";
  else state.form.voiceId = selected;
  voice.onchange = () => {
    state.form.voiceId = voice.value;
    if (gptSelected) {
      void saveTtsPreference("tts.gpt-sovits", null, voice.value || null)
        .catch((error) => showError("studio-error", errorText(error)));
    }
  };
  byId("speech-voice-label").textContent = t(gptSelected ? "gptReference" : "voice");
  byId("speech-voice-add").textContent = t(gptSelected ? "gptReferenceAdd" : "voiceAdd");
  byId("speech-style-fields").hidden = gptSelected;

  state.transcribeAudio = audioSlot(state.transcribeAudio);
  renderAudioInput(byId("transcribe-audio"), state.transcribeAudio, {rerender: renderStudio});

  /* 保存したボイスを使うと、その素性（組み込み/デザイン/クローン）で読み上げる。
     組み込みのままなら、詳細モードで話者だけを選べる。 */
  byId("speech-voice-note").textContent = t(gptSelected ? "gptReferenceNote" : "voiceNoteBuiltIn");
  const speaker = byId("advanced-speaker");
  if (speaker) {
    speaker.disabled = Boolean(state.form.voiceId);
    speaker.closest(".advanced").hidden = gptSelected;
  }

  const submit = byId("studio-submit");
  submit.textContent = state.task === "transcribe" ? t("transcribeAction") : t("create");
  const gated = renderCapabilityGate();
  submit.dataset.unavailable = String(gated);
  submit.disabled = gated;

  /* 種類・雰囲気を足した結果は、隠さずに書いた欄のすぐ下へ出す。 */
  for (const [id, task] of [["sfx-prompt-preview", "sfx"], ["music-prompt-preview", "music"]]) {
    const node = byId(id);
    if (!node) continue;
    const preview = state.task === task ? composedPrompt() : "";
    const base = String(byId(`${task}-prompt`)?.value || "").trim();
    node.textContent = preview && preview !== base ? `${t("promptPreview")}: ${preview}` : "";
  }
}

function capability(id) {
  return state.capabilities?.capabilities?.find((item) => item.id === id) || null;
}

function renderServicePill() {
  const pill = byId("service-pill");
  const required = (state.setup?.state || state.capabilities?.service?.state) === "setup_required";
  pill.textContent = serviceStateLabel();
  pill.classList.toggle("warn", required);
  /* 携帯ではヘッダの pill を畳んでいる。準備が要ることは、設定の入口の印で伝える。 */
  byId("nav-settings").dataset.attention = String(required);
}

function serviceStateLabel() {
  const value = state.setup?.state || state.capabilities?.service?.state;
  if (value === "available") return t("localOnly");
  if (value === "setup_required") return t("stateSetupRequired");
  return t("localOnly");
}

function renderCapabilityGate() {
  const gate = byId("capability-gate");
  const id = state.task === "sfx" ? currentSfxKind().task : TASK_CAPABILITY[state.task];
  const value = capability(id);
  const blocked = Boolean(value) && value.state !== "available";
  gate.hidden = !blocked;
  if (!blocked) return false;
  const component = CAPABILITY_COMPONENT[id];
  const label = SETUP_COMPONENTS.find((item) => item.id === component);
  byId("capability-gate-title").textContent = t("setupRequired");
  byId("capability-gate-reason").textContent = label
    ? `${t(label.label)} — ${t(label.detail)}`
    : (value.reason || value.reason_code || "");
  byId("capability-gate-action").onclick = () => activate("settings");
  return true;
}

/* ── 音声の取り込み ───────────────────────────────────────────────────── */
/* 元の音声は、ブラウザのマイクか、端末のファイル選択から取る。ControlDeck の
   ピッカーはプロジェクト内の素材には正しいが、まだどこにも保存されていない
   録音には届かず、携帯では利用者の期待するピッカーでもない。
   受け取った音は SonicForge 側で WAV に整えるので、端末ごとの録音形式の違い
   （iOS は webm を吐かず mp4 を吐く）はここで吸収できる。 */

function audioSlot(value) {
  return value || {uploadId: "", name: "", busy: false, recording: false, error: "", note: ""};
}

function isRecordingSupported() {
  return Boolean(navigator.mediaDevices?.getUserMedia) && typeof MediaRecorder !== "undefined";
}

function recorderMimeType() {
  for (const candidate of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]) {
    if (MediaRecorder.isTypeSupported?.(candidate)) return candidate;
  }
  return "";
}

async function uploadAudioBlob(blob, filename) {
  const form = new FormData();
  form.append("file", blob, filename);
  /* content-type は境界文字列を含むのでブラウザに決めさせる。 */
  return api("/uploads", {method: "POST", body: form});
}

function renderAudioInput(container, slot, {rerender, onUploaded}) {
  if (!container) return;
  container.replaceChildren();
  const row = document.createElement("div");
  row.className = "audio-input-row";

  const record = document.createElement("button");
  record.type = "button";
  record.className = slot.recording ? "cta-secondary recording" : "cta-secondary";
  record.textContent = slot.recording ? t("recordStop") : `\u{1F3A4} ${t("recordStart")}`;
  record.disabled = slot.busy || !isRecordingSupported();
  record.onclick = () => (slot.recording ? stopRecording(slot, {rerender, onUploaded}) : startRecording(slot, {rerender, onUploaded}));

  const choose = document.createElement("label");
  choose.className = "dropzone";
  choose.textContent = slot.name || `\u{1F4C1} ${t("chooseFile")}`;
  if (slot.uploadId) choose.classList.add("filled");
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "audio/*,video/mp4,.m4a,.wav,.mp3,.ogg,.webm,.flac";
  input.hidden = true;
  input.onchange = () => {
    const file = input.files?.[0];
    if (file) void acceptAudioFile(slot, file, {rerender, onUploaded});
  };
  choose.append(input);

  row.append(record, choose);
  container.append(row);

  if (slot.uploadId) {
    const clear = document.createElement("button");
    clear.type = "button";
    clear.textContent = t("removeAudio");
    clear.onclick = () => {
      Object.assign(slot, audioSlot(null));
      rerender();
    };
    row.append(clear);
  }

  const status = document.createElement("p");
  status.className = slot.error ? "error" : "hint";
  status.setAttribute("role", "status");
  status.textContent = slot.error
    || slot.note
    || (slot.busy ? t("uploading") : "")
    || (slot.recording ? t("recording") : "")
    || (slot.uploadId ? t("audioReady") : "")
    || (isRecordingSupported() ? "" : t("recordUnsupported"));
  if (status.textContent) container.append(status);
}

async function acceptAudioFile(slot, file, {rerender, onUploaded}) {
  slot.busy = true;
  slot.error = "";
  slot.note = "";
  rerender();
  try {
    const created = await uploadAudioBlob(file, file.name || "audio");
    slot.uploadId = created.upload_id;
    slot.name = created.filename;
    if (onUploaded) await onUploaded(slot);
  } catch (error) {
    slot.uploadId = "";
    slot.name = "";
    slot.error = errorText(error);
  } finally {
    slot.busy = false;
    rerender();
  }
}

/* 埋め込み枠は不透明 origin で動く。ブラウザはそこに getUserMedia を許さず、
   allow="microphone" を足しても SecurityError のままなので、許可を促しても直らない。
   そこでは host がマイクを開き、PCM だけを bridge の event で送ってくる。 */
const HOST_CAPTURE_RATE = 16000;
const hostCapture = {recordingId: "", sink: null};

function hostCaptureAvailable() { return Boolean(state.bridgePort); }

function decodePcmFrame(encoded) {
  const binary = atob(String(encoded || ""));
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return new Int16Array(bytes.buffer, 0, bytes.byteLength >> 1);
}

function receiveHostAudioFrame(data) {
  if (!hostCapture.sink || !data || data.recording_id !== hostCapture.recordingId) return;
  hostCapture.sink(decodePcmFrame(data.pcm), Number(data.peak) || 0);
}

async function startHostCapture(sink) {
  if (hostCapture.recordingId) throw new Error("already recording");
  const started = await callHost("host.audio.record.start", {});
  hostCapture.recordingId = String(started.recording_id || "");
  hostCapture.sink = sink;
  return started;
}

async function stopHostCapture() {
  const id = hostCapture.recordingId;
  hostCapture.recordingId = "";
  hostCapture.sink = null;
  if (!id) return null;
  return await callHost("host.audio.record.stop", {recording_id: id}).catch(() => null);
}

/* 集めた PCM をそのまま WAV にする。ワーカーは素の波形しか読まないので、
   容器を挟まないこの形が一番取り違えが少ない。 */
function pcmToWav(chunks, rate) {
  let total = 0;
  for (const chunk of chunks) total += chunk.length;
  const buffer = new ArrayBuffer(44 + total * 2);
  const view = new DataView(buffer);
  const ascii = (offset, text) => { for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i)); };
  ascii(0, "RIFF"); view.setUint32(4, 36 + total * 2, true); ascii(8, "WAVE");
  ascii(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  ascii(36, "data"); view.setUint32(40, total * 2, true);
  let offset = 44;
  for (const chunk of chunks) {
    for (let index = 0; index < chunk.length; index += 1) { view.setInt16(offset, chunk[index], true); offset += 2; }
  }
  return new Blob([buffer], {type: "audio/wav"});
}

function micErrorText(error) {
  return error?.name === "SecurityError" ? t("micBlockedInFrame") : t("micDenied");
}

async function startRecording(slot, handlers) {
  slot.error = "";
  slot.note = "";
  /* ControlDeck の中ではマイクを開けないので、host に開いてもらって
     PCM を受け取る。単体で開いているときは今までどおり自分で録る。 */
  if (hostCaptureAvailable()) return startHostRecording(slot, handlers);
  if (!isRecordingSupported()) {
    slot.error = t("recordUnsupported");
    handlers.rerender();
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio: true});
  } catch (error) {
    slot.error = micErrorText(error);
    handlers.rerender();
    return;
  }
  const mimeType = recorderMimeType();
  const recorder = new MediaRecorder(stream, mimeType ? {mimeType} : undefined);
  const chunks = [];
  recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data); };
  recorder.onstop = async () => {
    for (const track of stream.getTracks()) track.stop();
    slot.recording = false;
    slot.recorder = null;
    const type = recorder.mimeType || mimeType || "audio/webm";
    const extension = type.includes("mp4") ? "m4a" : "webm";
    const blob = new Blob(chunks, {type});
    if (!blob.size) { handlers.rerender(); return; }
    await acceptAudioFile(slot, new File([blob], `recording.${extension}`, {type}), handlers);
  };
  slot.recorder = recorder;
  slot.recording = true;
  recorder.start();
  handlers.rerender();
}

async function startHostRecording(slot, handlers) {
  const chunks = [];
  try {
    await startHostCapture((frame) => chunks.push(frame));
  } catch (error) {
    slot.error = error?.message || t("micDenied");
    handlers.rerender();
    return;
  }
  slot.recording = true;
  slot.hostChunks = chunks;
  handlers.rerender();
}

function stopRecording(slot, handlers) {
  if (slot.hostChunks) {
    const chunks = slot.hostChunks;
    slot.hostChunks = null;
    slot.recording = false;
    handlers.rerender();
    void stopHostCapture().then(() => {
      const blob = pcmToWav(chunks, HOST_CAPTURE_RATE);
      if (blob.size <= 44) { handlers.rerender(); return; }
      return acceptAudioFile(slot, new File([blob], "recording.wav", {type: "audio/wav"}), handlers);
    });
    return;
  }
  try { slot.recorder?.stop(); } catch { /* すでに止まっている */ }
  slot.recording = false;
  handlers.rerender();
}

async function pickProjectOutput() {
  try {
    const grant = await callHost("host.files.export", {suggested_name: ""});
    const id = grant?.grant_id || grant?.export_grant_id;
    if (!id) return;
    state.projectGrant = id;
    syncAdvanced();
  } catch (error) {
    /* 選ぶのをやめただけなら、それは失敗ではない。機械語のコードを出さない。 */
    if (isPickerDismissal(error)) return;
    showError("studio-error", error?.code === "bridge_unavailable" ? t("bridgeOnly") : errorText(error));
  }
}

/* ピッカーを閉じただけの合図。ホストの実装差を 1 か所に閉じ込める。 */
function isPickerDismissal(error) {
  const code = String(error?.code || error?.message || error || "");
  return /cancel|dismiss|abort/i.test(code);
}

function showError(id, message) {
  const node = byId(id);
  if (!node) return;
  node.hidden = !message;
  node.textContent = message || "";
}

/* ── 生成の受付 ───────────────────────────────────────────────────────── */

function commonRequestParts() {
  const form = state.form;
  const sampleRate = form.sampleRate ? Number(form.sampleRate) : null;
  const channels = form.channels ? Number(form.channels) : null;
  const seed = form.seed !== undefined && form.seed !== "" ? Number(form.seed) : null;
  return {
    profile: (form.profile || "").trim() || "default",
    quality: form.quality || "balanced",
    output: {
      format: form.format || "wav",
      sample_rate: Number.isFinite(sampleRate) ? sampleRate : null,
      channels: Number.isFinite(channels) ? channels : null,
    },
    routing: {
      engine: (form.engine || "").trim() || null,
      model: (form.model || "").trim() || null,
      device: form.device || "auto",
    },
    seed: Number.isFinite(seed) ? seed : null,
    project_output_grant: state.projectGrant || null,
  };
}

function buildRequest() {
  const shared = commonRequestParts();
  if (state.task === "speech") {
    const text = String(byId("speech-text").value || "").trim();
    if (!text) throw new Error(t("needText"));
    const preset = SPEECH_STYLES.find((item) => item.id === (state.form.speechStyle || "auto"));
    const instruction = String(state.form.styleInstruction || "").trim() || preset?.instruction || "";
    const input = {text};
    const gptSelected = (state.ttsPreferences?.engine_id || "tts.qwen3") === "tts.gpt-sovits";
    if (state.form.voiceId) input.voice_id = state.form.voiceId;
    /* 保存したボイスを選んでいないときだけ、組み込みの話者を直接指定できる。
       保存したボイスは自分の素性と話者を持っているので上書きしない。 */
    if (!gptSelected && !state.form.voiceId && state.form.speaker) input.speaker = state.form.speaker;
    if (!gptSelected && instruction) input.style = {preset: preset?.id || "auto", instruction};
    if (gptSelected) {
      const selectedVoice = state.voices.find((item) => item.id === state.form.voiceId);
      const selectedModel = state.ttsModels.find((item) => item.active);
      const modelHasReference = Boolean(selectedModel?.has_reference);
      if ((!selectedVoice || selectedVoice.source_type !== "clone") && !modelHasReference) {
        throw new Error(t("gptVoiceRequired"));
      }
    }
    return {...shared, routing: {
      ...shared.routing,
      engine: state.ttsPreferences?.engine_id || "tts.qwen3",
      model: (state.ttsPreferences?.engine_id === "tts.gpt-sovits")
        ? (state.ttsPreferences?.gpt_sovits_model_id || "lj1995/GPT-SoVITS")
        : shared.routing.model,
    }, task: "speech.tts.synthesize", input,
      content_language: state.form.speechLanguage || "auto"};
  }
  if (state.task === "transcribe") {
    const slot = audioSlot(state.transcribeAudio);
    if (!slot.uploadId) throw new Error(t("needAudio"));
    return {...shared, task: "speech.asr.transcribe",
      input: {upload_id: slot.uploadId},
      content_language: state.form.transcribeLanguage || "auto"};
  }
  if (state.task === "sfx") {
    const prompt = composedPrompt();
    if (!prompt) throw new Error(t("needPrompt"));
    return {...shared, task: currentSfxKind().task,
      input: {prompt, duration_sec: currentDuration()},
      content_language: "auto"};
  }
  const prompt = composedPrompt();
  if (!prompt) throw new Error(t("needPrompt"));
  const bpm = state.form.bpm ? Number(state.form.bpm) : null;
  return {...shared, task: "music.generate",
    input: {
      prompt,
      duration_sec: currentDuration(),
      bpm: Number.isFinite(bpm) && bpm ? bpm : null,
      instrumental: byId("music-instrumental").checked,
    },
    content_language: "auto"};
}

byId("studio-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("studio-error", "");
  let request;
  try { request = buildRequest(); } catch (error) { showError("studio-error", errorText(error)); return; }
  const submit = byId("studio-submit");
  submit.disabled = true;
  setHostBusy(true);
  try {
    const created = await jsonPost("/tasks", request);
    state.activeJob = created.job_id;
    await showJob(created.job_id);
  } catch (error) {
    showError("studio-error", errorText(error));
  } finally {
    setHostBusy(false);
    submit.disabled = false;
  }
});

byId("studio-reset").addEventListener("click", () => {
  state.form = {};
  state.projectGrant = "";
  state.transcribeAudio = null;
  byId("speech-text").value = "";
  byId("sfx-prompt").value = "";
  byId("music-prompt").value = "";
  showError("studio-error", "");
  mountAdvanced();
  renderStudio();
});

for (const id of ["sfx-prompt", "music-prompt"]) {
  byId(id).addEventListener("input", () => renderStudio());
}

byId("speech-voice-add").addEventListener("click", () => {
  if ((state.ttsPreferences?.engine_id || "tts.qwen3") === "tts.gpt-sovits") {
    activate("settings");
    byId("gpt-sample-preset")?.focus();
    return;
  }
  openVoiceDialog();
});

/* ── ジョブの追跡 ─────────────────────────────────────────────────────── */

function jobStateLabel(value) {
  return {
    queued: t("stateQueued"), running: t("stateRunning"), succeeded: t("stateSucceeded"),
    failed: t("stateFailed"), canceled: t("stateCanceled"),
  }[value] || value;
}

function jobTaskLabel(task) {
  return {
    "speech.tts.synthesize": t("taskSpeech"),
    "speech.asr.transcribe": t("taskTranscribe"),
    "speech.localization.batch": t("taskLocalization"),
    "audio.sfx.generate": t("taskSfx"),
    "audio.ambience.generate": t("sfxAmbience"),
    "music.generate": t("taskMusic"),
    "audio.export": t("exportAsset"),
    "audio.process": t("stageProcess"),
    "pipeline.execute": t("pipelineTitle"),
    "system.setup": t("setUp"),
  }[task] || task;
}

async function showJob(id) {
  let job;
  try { job = await api(`/jobs/${encodeURIComponent(id)}`); }
  catch { if (!socketOpen()) setTimeout(() => showJob(id), 3000); return; }
  if (ACTIVE_STATES.has(job.state)) state.activeJob = id;
  renderJobStage(job);
  renderMiniProgress(job);
  if (ACTIVE_STATES.has(job.state)) {
    if (!socketOpen()) setTimeout(() => showJob(id), 2000);
    return;
  }
  if (state.activeJob === id) state.activeJob = "";
  /* 資産の見出しはジョブの task から引く。順番を逆にすると、できたばかりの
     ものだけが生の asset ID で並ぶ。 */
  await loadActiveJobs();
  await loadAssets();
  notifyFinished(job);
}

function notifyFinished(job) {
  if (!state.bridgePort || job.state === "canceled") return;
  void callHost("host.notification.show", {
    title: "SonicForge",
    message: job.state === "succeeded" ? t("done") : (job.error_message || t("failed")),
    level: job.state === "succeeded" ? "success" : "error",
    dedupe_key: job.id,
  }).catch(() => {});
}

function renderJobStage(job) {
  state.lastJob = job;
  const progress = byId("stage-progress");
  const result = byId("stage-result");
  const active = ACTIVE_STATES.has(job.state);
  progress.hidden = !active;
  if (active) {
    byId("progress-phase").textContent = job.state === "queued" ? t("queued") : t("running");
    const bar = byId("progress-bar");
    const fraction = Number(job.progress || 0);
    bar.classList.toggle("indeterminate", fraction <= 0);
    bar.style.width = fraction > 0 ? `${Math.round(fraction * 100)}%` : "";
    byId("progress-detail").textContent = job.result?.message || jobTaskLabel(job.task);
    byId("progress-cancel").onclick = () => cancelJob(job.id);
    result.hidden = true;
    return;
  }
  if (job.state !== "succeeded") {
    result.hidden = true;
    showError("studio-error", jobFailureText(job));
    return;
  }
  showError("studio-error", "");
  const assetId = job.result?.asset_id;
  const text = job.result?.text;
  result.hidden = false;
  byId("result-title").textContent = `${jobTaskLabel(job.task)} — ${t("done")}`;
  const audio = byId("result-audio");
  audio.hidden = !assetId;
  if (assetId) audio.src = apiUrl(`/assets/${encodeURIComponent(assetId)}/content`);
  const transcript = byId("result-text");
  transcript.hidden = !text;
  if (text) transcript.textContent = transcriptText(job.result);
  byId("result-meta").textContent = job.result?.language ? `${t("contentLanguage")}: ${job.result.language}` : "";
  byId("result-export").hidden = !assetId;
  byId("result-export").onclick = () => openExport(assetId);
  byId("result-detail").hidden = !assetId;
  byId("result-detail").onclick = () => openAssetDetail(assetId);
  byId("result-again").onclick = () => byId("studio-form").requestSubmit();
}

/* 区切りごとの時刻は、返ってきたときだけ添える。無い経路で嘘の時刻は出さない。 */
function transcriptText(result) {
  const segments = Array.isArray(result?.segments) ? result.segments : [];
  if (!segments.length || state.form.timestamps === false) return String(result?.text || "");
  return segments.map((segment) => {
    const start = Number(segment.start ?? segment.start_ms / 1000 ?? 0);
    const end = Number(segment.end ?? segment.end_ms / 1000 ?? 0);
    return `[${start.toFixed(1)}-${end.toFixed(1)}] ${String(segment.text || "").trim()}`;
  }).join("\n");
}

function renderMiniProgress(job) {
  const bar = byId("mini-progress");
  const active = ACTIVE_STATES.has(job.state);
  bar.hidden = !active;
  if (!active) return;
  byId("mini-phase").textContent = `${jobTaskLabel(job.task)} — ${jobStateLabel(job.state)}`;
  const fraction = Number(job.progress || 0);
  const inner = byId("mini-bar");
  inner.classList.toggle("indeterminate", fraction <= 0);
  inner.style.width = fraction > 0 ? `${Math.round(fraction * 100)}%` : "";
  byId("mini-cancel").onclick = () => cancelJob(job.id);
}

async function cancelJob(id) {
  try { await api(`/jobs/${encodeURIComponent(id)}`, {method: "DELETE"}); }
  catch (error) { showError("studio-error", errorText(error)); return; }
  await showJob(id);
}

async function loadActiveJobs() {
  try {
    const data = await api("/jobs?limit=100");
    state.jobs = data.jobs || [];
  } catch { return; }
  const active = state.jobs.filter((job) => ACTIVE_STATES.has(job.state));
  const badge = byId("activity-badge");
  badge.hidden = active.length === 0;
  badge.textContent = String(active.length);
  if (active.length && !state.activeJob) {
    state.activeJob = active[0].id;
    await showJob(active[0].id);
  } else if (!active.length) {
    byId("mini-progress").hidden = true;
  }
  renderActivity();
  renderLibrary();
  renderRecent();
}

function renderActivity() {
  const rows = byId("activity-rows");
  if (!rows) return;
  byId("activity-count").textContent = state.jobs.length ? `${state.jobs.length}${t("itemCount")}` : "";
  byId("activity-empty").hidden = state.jobs.length > 0;
  rows.replaceChildren(...state.jobs.map((job) => {
    const row = document.createElement("div");
    row.className = "row";
    row.dataset.status = job.state;
    const left = document.createElement("div");
    const title = document.createElement("div");
    title.className = "t";
    title.textContent = jobTaskLabel(job.task);
    const sub = document.createElement("div");
    sub.className = "s";
    sub.textContent = job.error_message || job.result?.text?.slice(0, 120) || job.id;
    left.append(title, sub);
    const side = document.createElement("div");
    side.className = "row-side";
    const badge = document.createElement("span");
    badge.className = "state";
    badge.dataset.tone = job.state === "failed" ? "bad" : (ACTIVE_STATES.has(job.state) ? "warn" : "muted");
    badge.textContent = jobStateLabel(job.state);
    side.append(badge);
    if (ACTIVE_STATES.has(job.state)) {
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.textContent = t("cancel");
      cancel.onclick = () => cancelJob(job.id);
      side.append(cancel);
    } else if (job.result?.asset_id) {
      const open = document.createElement("button");
      open.type = "button";
      open.textContent = t("details");
      open.onclick = () => openAssetDetail(job.result.asset_id);
      side.append(open);
    }
    row.append(left, side);
    return row;
  }));
}

/* ── ライブラリ ───────────────────────────────────────────────────────── */

const LIBRARY_FILTERS = [
  {id: "all", label: "filter"},
  {id: "speech.tts.synthesize", label: "taskSpeech"},
  {id: "audio.sfx.generate", label: "taskSfx"},
  {id: "music.generate", label: "taskMusic"},
];

async function loadAssets() {
  try {
    const data = await api("/assets?limit=200");
    state.assets = data.assets || [];
    showError("library-error", "");
  } catch (error) {
    showError("library-error", errorText(error));
    return;
  }
  renderLibrary();
  renderRecent();
}

function assetTask(asset) {
  const job = state.jobs.find((item) => item.id === asset.job_id);
  return job?.task || "";
}

function renderLibrary() {
  const grid = byId("library-grid");
  if (!grid) return;
  renderChips(byId("library-filter"), LIBRARY_FILTERS.map((item) => ({
    id: item.id,
    text: item.id === "all" ? (state.locale === "ja" ? "すべて" : "All") : t(item.label),
  })), state.libraryFilter, (value) => { state.libraryFilter = value; renderLibrary(); });

  const items = state.assets.filter((asset) => {
    if (state.libraryFilter === "all") return true;
    const task = assetTask(asset);
    if (state.libraryFilter === "audio.sfx.generate") return task.startsWith("audio.");
    return task === state.libraryFilter;
  });
  byId("library-count").textContent = `${items.length}${t("itemCount")}`;
  byId("library-empty").hidden = items.length > 0;
  grid.replaceChildren(...items.map((asset) => {
    const card = document.createElement("div");
    card.className = "card";
    const heading = document.createElement("h3");
    heading.textContent = jobTaskLabel(assetTask(asset)) || t("audioAsset");
    const tags = document.createElement("div");
    tags.className = "tags";
    for (const value of [formatSeconds(asset.duration_ms),
      asset.sample_rate ? `${asset.sample_rate} Hz` : null,
      asset.channels === 2 ? "stereo" : "mono",
      formatBytes(asset.size_bytes)]) {
      if (!value || value === "—") continue;
      const tag = document.createElement("span");
      tag.textContent = value;
      tags.append(tag);
    }
    const player = document.createElement("audio");
    player.controls = true;
    player.preload = "none";
    player.src = apiUrl(`/assets/${encodeURIComponent(asset.id)}/content`);
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = asset.created_at ? new Date(asset.created_at).toLocaleString() : "";
    const actions = document.createElement("div");
    actions.className = "actions";
    const exportButton = document.createElement("button");
    exportButton.type = "button";
    exportButton.textContent = t("exportAsset");
    exportButton.onclick = () => openExport(asset.id);
    const detailButton = document.createElement("button");
    detailButton.type = "button";
    detailButton.textContent = t("details");
    detailButton.onclick = () => openAssetDetail(asset.id);
    actions.append(exportButton, detailButton);
    card.append(heading, tags, player, meta, actions);
    return card;
  }));
}

function renderRecent() {
  const strip = byId("recent-strip");
  if (!strip) return;
  const items = state.assets.slice(0, 5);
  byId("recent-empty").hidden = items.length > 0;
  strip.replaceChildren(...items.map((asset) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "strip-item";
    const title = document.createElement("span");
    title.className = "t";
    title.textContent = jobTaskLabel(assetTask(asset)) || t("audioAsset");
    const sub = document.createElement("span");
    sub.className = "s";
    sub.textContent = formatSeconds(asset.duration_ms);
    button.append(title, sub);
    button.onclick = () => openAssetDetail(asset.id);
    return button;
  }));
}

/* ── 書き出し ─────────────────────────────────────────────────────────── */

async function loadDeliveryProfiles() {
  if (state.deliveryProfiles.length) return;
  try {
    const data = await api("/delivery/audio/profiles");
    state.deliveryProfiles = data.profiles || [];
  } catch { state.deliveryProfiles = []; }
}

async function openExport(assetId) {
  if (!assetId) return;
  state.exportAssetId = assetId;
  await loadDeliveryProfiles();
  const select = byId("export-profile");
  select.replaceChildren(...state.deliveryProfiles.map((profile) => {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = profile.label;
    return option;
  }));
  const describe = () => {
    const profile = state.deliveryProfiles.find((item) => item.id === select.value);
    byId("export-purpose").textContent = profile?.purpose || "";
    byId("export-filename").placeholder = `${assetId.split(":").pop()}${profile?.extension || ""}`;
  };
  select.onchange = describe;
  describe();
  byId("export-summary").textContent = assetId;
  showError("export-error", "");
  byId("export-dialog").showModal();
}

byId("export-cancel").addEventListener("click", () => byId("export-dialog").close());
byId("export-confirm").addEventListener("click", async () => {
  const body = {profile: byId("export-profile").value};
  const filename = String(byId("export-filename").value || "").trim();
  if (filename) body.filename = filename;
  if (byId("export-to-project").checked) {
    try {
      const grant = await callHost("host.files.export", {suggested_name: filename || ""});
      const id = grant?.grant_id || grant?.export_grant_id;
      if (!id) return;
      body.project_output_grant = id;
    } catch (error) {
      showError("export-error", error?.code === "bridge_unavailable" ? t("bridgeOnly") : errorText(error));
      return;
    }
  }
  try {
    const created = await jsonPost(`/assets/${encodeURIComponent(state.exportAssetId)}/export`, body);
    byId("export-dialog").close();
    state.activeJob = created.job_id;
    await showJob(created.job_id);
  } catch (error) {
    showError("export-error", errorText(error));
  }
});

async function openAssetDetail(assetId) {
  let asset;
  try { asset = await api(`/assets/${encodeURIComponent(assetId)}`); }
  catch (error) { showError("library-error", errorText(error)); return; }
  const facts = [
    [t("length"), formatSeconds(asset.duration_ms)],
    [t("sampleRate"), asset.sample_rate ? `${asset.sample_rate} Hz` : "—"],
    [t("channels"), asset.channels === 2 ? "stereo" : "mono"],
    ["SHA-256", String(asset.sha256 || "").slice(0, 16)],
    [t("engine"), asset.provenance?.engine_id || "—"],
    [t("model"), asset.provenance?.model_id || "—"],
    [t("quality"), asset.provenance?.parameters?.quality || "—"],
    [t("seed"), asset.provenance?.parameters?.seed ?? "—"],
  ];
  byId("detail-facts").replaceChildren(...facts.map(([key, value]) => {
    const wrap = document.createElement("div");
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    wrap.append(dt, dd);
    return wrap;
  }));
  byId("detail-raw").textContent = JSON.stringify(asset.provenance || asset.metadata || {}, null, 2);
  byId("detail-dialog").showModal();
}
byId("detail-close").addEventListener("click", () => byId("detail-dialog").close());

/* ── 設定：ランタイム ─────────────────────────────────────────────────── */

async function loadCapabilities() {
  try { state.capabilities = await api("/capabilities"); } catch { return; }
  renderServicePill();
  renderStudio();
  renderSettings();
}

/* 使えるモデルはサーバが知っている。ここで名前を並べておかないと、詳細は
   Hugging Face のリポジトリ名を打ち込む欄のままで、事実上だれも選べない。 */
async function loadModels() {
  try { state.models = await api("/models"); } catch { return; }
  renderStudio();
}

async function loadTtsSettings() {
  try {
    const [preferences, models, samples] = await Promise.all([
      api("/tts/preferences"),
      api("/tts/models"),
      api("/tts/samples"),
    ]);
    state.ttsPreferences = preferences;
    state.ttsModels = models.models || [];
    state.ttsSamples = samples.samples || [];
    showError("tts-model-error", "");
  } catch (error) {
    showError("tts-model-error", errorText(error));
    return;
  }
  renderStudio();
  renderTtsModels();
  renderTtsSamplePreset();
}

async function saveTtsPreference(engineId, modelId = null, voiceId = undefined) {
  const body = {
    engine_id: engineId,
    gpt_sovits_model_id: modelId || state.ttsPreferences?.gpt_sovits_model_id || null,
    gpt_sovits_voice_id: voiceId === undefined ? (state.ttsPreferences?.gpt_sovits_voice_id || null) : voiceId,
  };
  state.ttsPreferences = await api("/tts/preferences", {
    method: "PUT",
    headers: {"content-type": "application/json"},
    body: JSON.stringify(body),
  });
  renderStudio();
  renderTtsModels();
}

async function loadSetup() {
  try {
    state.setup = await api("/setup/status");
    showError("setup-error", "");
  } catch (error) {
    showError("setup-error", errorText(error));
    return;
  }
  renderServicePill();
  renderSettings();
}

function componentState(id) {
  return state.setup?.components?.find((item) => item.id === id)?.state || "missing";
}

function stateLabel(value) {
  return {
    available: t("stateAvailable"), preparing: t("statePreparing"),
    setup_required: t("stateSetupRequired"), missing: t("stateSetupRequired"),
    failed: t("stateFailed"), unavailable: t("stateUnavailable"),
  }[value] || value;
}

function setLocale(locale) {
  state.locale = locale === "en" ? "en" : "ja";
  state.localeFromHost = false;
  remember("locale", state.locale);
  applyLocale();
}

function renderSettings() {
  /* 表示言語は、狭い画面ではヘッダに置けない。設定に「表示言語」として
     並べておけば、地球のアイコンより何であるかが分かる。 */
  renderChips(
    byId("locale-chips"),
    [{id: "ja", text: "日本語"}, {id: "en", text: "English"}],
    state.locale,
    setLocale,
  );
  const rows = byId("setup-rows");
  if (!rows) return;
  rows.replaceChildren(...SETUP_COMPONENTS.map((component) => {
    const value = componentState(component.id);
    const row = document.createElement("div");
    row.className = "row";
    const left = document.createElement("div");
    const title = document.createElement("div");
    title.className = "t";
    title.textContent = t(component.label);
    left.append(title);
    if (component.detail) {
      const sub = document.createElement("div");
      sub.className = "s";
      sub.textContent = t(component.detail);
      left.append(sub);
    }
    if (component.id === "game-audio" && value !== "available") {
      left.append(gatedCredentialBlock(component.id));
      const terms = document.createElement("label");
      terms.className = "check";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.id = "stability-terms";
      const text = document.createElement("span");
      text.textContent = t("termsStability");
      terms.append(input, text);
      left.append(terms);
    }
    const side = document.createElement("div");
    side.className = "row-side";
    const badge = document.createElement("span");
    badge.className = "state";
    badge.dataset.tone = value === "available" ? "ok" : (value === "failed" ? "bad" : "warn");
    badge.textContent = stateLabel(value);
    side.append(badge);
    if (component.profile) {
      if (value !== "available") {
        const setup = document.createElement("button");
        setup.type = "button";
        setup.className = "cta-secondary";
        setup.textContent = t("setUp");
        setup.onclick = () => applySetup(component.profile, "apply");
        side.append(setup);
      } else if (state.mode === "advanced") {
        for (const [key, endpoint] of [["repair", "repair"], ["update", "update"]]) {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = t(key);
          button.onclick = () => applySetup(component.profile, endpoint);
          side.append(button);
        }
      }
    }
    row.append(left, side);
    return row;
  }));

  const profileSelect = byId("setup-profile");
  if (profileSelect && !profileSelect.dataset.ready) {
    profileSelect.dataset.ready = "1";
    profileSelect.onchange = () => void loadPlan();
  }
  if (profileSelect) {
    const current = profileSelect.value || "speech-essentials";
    profileSelect.replaceChildren(...SETUP_PROFILES.map((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = t(item.label);
      return option;
    }));
    profileSelect.value = current;
  }
  renderPlan();
  renderCapabilityRows();
  renderVoices();
  renderTtsModels();
}

/* Hugging Face が gate している配布物は、ライセンス同意だけでは降りてこない。
   同意したアカウントのトークンが要る、という事実をここで初めて出す。 */
function gatedCredentialBlock(componentId) {
  const block = document.createElement("div");
  block.className = "gate";
  const gated = (state.credentials?.gated_models || []).filter((item) => item.component === componentId);
  if (!gated.length) return block;
  const title = document.createElement("b");
  title.textContent = t("hfTokenLabel");
  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent = t("hfTokenHint");
  block.append(title, hint);

  for (const model of gated) {
    const link = document.createElement("a");
    link.href = model.url;
    link.target = "_blank";
    link.rel = "noreferrer noopener";
    link.textContent = `${t("openModelPage")}: ${model.repo}`;
    link.className = "hint";
    block.append(link);
  }

  const row = document.createElement("div");
  row.className = "audio-input-row";
  const input = document.createElement("input");
  input.type = "password";
  input.autocomplete = "off";
  input.id = "hf-token";
  input.placeholder = state.credentials?.huggingface_token_set ? t("hfTokenSet") : "hf_…";
  const save = document.createElement("button");
  save.type = "button";
  save.className = "cta-secondary";
  save.textContent = t("hfTokenSave");
  save.onclick = () => void saveHuggingFaceToken(input.value);
  row.append(input, save);
  if (state.credentials?.huggingface_token_set) {
    const clear = document.createElement("button");
    clear.type = "button";
    clear.textContent = t("hfTokenClear");
    clear.onclick = () => void saveHuggingFaceToken("");
    row.append(clear);
  }
  block.append(row);
  return block;
}

async function saveHuggingFaceToken(token) {
  try {
    state.credentials = await api("/setup/credentials", {
      method: "PUT",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({huggingface_token: token}),
    });
    showError("setup-error", "");
  } catch (error) {
    showError("setup-error", errorText(error));
  }
  renderSettings();
}

async function loadCredentials() {
  try { state.credentials = await api("/setup/credentials"); } catch { return; }
  renderSettings();
}

async function loadPlan() {
  const profile = byId("setup-profile")?.value || "speech-essentials";
  try { state.plan = await api(`/setup/plan?profile=${encodeURIComponent(profile)}`); }
  catch (error) { showError("setup-error", errorText(error)); return; }
  renderPlan();
}

function renderPlan() {
  const facts = byId("setup-plan-facts");
  if (!facts) return;
  const plan = state.plan;
  const items = plan ? [
    [t("backend"), plan.backend],
    [t("platform"), plan.platform],
    [t("freeSpace"), formatBytes(plan.free_bytes)],
    [t("requiredSpace"), formatBytes(plan.required_bytes_estimate)],
  ] : [];
  facts.replaceChildren(...items.map(([key, value]) => {
    const wrap = document.createElement("div");
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = String(value ?? "—");
    wrap.append(dt, dd);
    return wrap;
  }));
  const warn = byId("setup-plan-warn");
  const notes = [...(plan?.warnings || []), ...(plan?.blockers || [])];
  warn.hidden = notes.length === 0;
  warn.textContent = notes.join(" · ");
  const apply = byId("setup-plan-apply");
  apply.disabled = Boolean(plan?.blockers?.length);
  apply.onclick = () => applySetup(byId("setup-profile").value, "apply");
}

async function applySetup(profile, endpoint) {
  const accepted = [];
  if (["game-audio", "full-studio"].includes(profile)) {
    if (!byId("stability-terms")?.checked && componentState("game-audio") !== "available") {
      showError("setup-error", t("termsRequired"));
      return;
    }
    accepted.push("stability-ai-community-license");
  }
  try {
    const created = await jsonPost(`/setup/${endpoint}`, {profile, components: [], accepted_terms: accepted});
    showError("setup-error", "");
    state.activeJob = created.job_id;
    await showJob(created.job_id);
  } catch (error) {
    showError("setup-error", errorText(error));
  }
}

function renderCapabilityRows() {
  const rows = byId("capability-rows");
  if (!rows) return;
  const items = state.capabilities?.capabilities || [];
  rows.replaceChildren(...items.map((item) => {
    const row = document.createElement("div");
    row.className = "row";
    const left = document.createElement("div");
    const title = document.createElement("div");
    title.className = "t";
    title.textContent = jobTaskLabel(item.id);
    const sub = document.createElement("div");
    sub.className = "s";
    sub.textContent = `${item.id} · ${Object.keys(item.features || {}).join(", ")}`;
    left.append(title, sub);
    const badge = document.createElement("span");
    badge.className = "state";
    badge.dataset.tone = item.state === "available" ? "ok" : "warn";
    badge.textContent = stateLabel(item.state);
    row.append(left, badge);
    return row;
  }));
  const facts = byId("diagnostics-facts");
  if (!facts) return;
  const service = state.capabilities?.service || {};
  const items2 = [
    ["service", `${service.id || "sonic-forge"} ${service.version || ""}`],
    ["api_version", state.capabilities?.api_version || "—"],
    [t("backend"), state.plan?.backend || "—"],
  ];
  facts.replaceChildren(...items2.map(([key, value]) => {
    const wrap = document.createElement("div");
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    wrap.append(dt, dd);
    return wrap;
  }));
}

/* ── 設定：TTS モデル ────────────────────────────────────────────────── */

function renderTtsModels() {
  const rows = byId("tts-model-rows");
  if (!rows) return;
  rows.replaceChildren(...state.ttsModels.map((model) => {
    const row = document.createElement("div");
    row.className = "row";
    const left = document.createElement("div");
    const title = document.createElement("div");
    title.className = "t";
    title.textContent = model.name;
    const sub = document.createElement("div");
    sub.className = "s";
    sub.textContent = [model.id, model.license_id, model.size_bytes ? formatBytes(model.size_bytes) : null]
      .filter(Boolean).join(" · ");
    left.append(title, sub);
    const side = document.createElement("div");
    side.className = "row-side";
    if (model.active) {
      const badge = document.createElement("span");
      badge.className = "state";
      badge.dataset.tone = "ok";
      badge.textContent = t("ttsModelActive");
      side.append(badge);
    } else {
      const activate = document.createElement("button");
      activate.type = "button";
      activate.className = "cta-secondary";
      activate.textContent = t("ttsModelActivate");
      activate.onclick = async () => {
        try {
          await api(`/tts/models/${encodeURIComponent(model.id)}/activate`, {method: "PUT"});
          await loadTtsSettings();
        } catch (error) { showError("tts-model-error", errorText(error)); }
      };
      side.append(activate);
    }
    if (!model.built_in) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = t("delete");
      remove.disabled = model.active;
      remove.title = model.active ? t("ttsModelDeleteActive") : "";
      remove.onclick = () => confirmAction(model.name, t("ttsModelDeleteBody"), async () => {
        await api(`/tts/models/${encodeURIComponent(model.id)}`, {method: "DELETE"});
        await loadTtsSettings();
      });
      side.append(remove);
    }
    row.append(left, side);
    return row;
  }));
}

byId("tts-model-upload").addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  const form = new FormData();
  form.append("file", file, file.name);
  try {
    await api("/tts/models/upload", {method: "POST", body: form});
    await loadTtsSettings();
  } catch (error) { showError("tts-model-error", errorText(error)); }
});

function renderTtsSamplePreset() {
  const select = byId("gpt-sample-preset");
  if (!select) return;
  const selected = select.value;
  select.replaceChildren(...[
    {id: "", name: t("gptSampleCustom")},
    ...state.ttsSamples.map((item) => ({id: item.id, name: item.name})),
  ].map((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.name;
    return option;
  }));
  select.value = state.ttsSamples.some((item) => item.id === selected) ? selected : "";
  const sample = state.ttsSamples.find((item) => item.id === select.value);
  const source = byId("gpt-sample-source");
  const terms = byId("gpt-sample-terms");
  source.hidden = !sample;
  terms.hidden = !sample;
  if (sample) {
    source.href = sample.source_url;
    source.textContent = t("gptSampleSource");
    terms.href = sample.terms_url;
    terms.textContent = t("gptSampleTerms");
  }
  byId("gpt-sample-source-note").textContent = sample
    ? t(sample.install_mode === "managed_download" ? "gptSampleManagedHint" : "gptSampleLocalHint")
    : "";
  byId("gpt-sample-file").disabled = sample?.install_mode === "managed_download";
  byId("gpt-sample-rights-label").textContent = t(sample ? "gptSampleAcceptTerms" : "voiceRights");
  byId("gpt-sample-add").textContent = t(sample?.installed_voice_id ? "gptSampleUse" : "gptSampleAdd");
}

byId("gpt-sample-preset").addEventListener("change", () => {
  const sample = state.ttsSamples.find((item) => item.id === byId("gpt-sample-preset").value);
  if (sample) {
    byId("gpt-sample-name").value = sample.name;
    byId("gpt-sample-language").value = sample.language;
    byId("gpt-sample-text").value = sample.reference_text;
  }
  renderTtsSamplePreset();
});

byId("gpt-sample-add").addEventListener("click", async () => {
  const sample = state.ttsSamples.find((item) => item.id === byId("gpt-sample-preset").value);
  const name = String(byId("gpt-sample-name").value || "").trim();
  const transcript = String(byId("gpt-sample-text").value || "").trim();
  const language = byId("gpt-sample-language").value || "ja";
  const file = byId("gpt-sample-file").files?.[0];
  const installedVoiceId = sample?.installed_voice_id || null;
  if (!installedVoiceId && (!name || !transcript || (!file && sample?.install_mode !== "managed_download") || !byId("gpt-sample-rights").checked)) {
    showError("gpt-sample-error", t("gptSampleRequired"));
    return;
  }
  try {
    let created;
    if (installedVoiceId) {
      created = {id: installedVoiceId};
    } else if (sample?.install_mode === "managed_download") {
      created = await jsonPost(`/tts/samples/${encodeURIComponent(sample.id)}/install`, {accepted_terms: true});
    } else {
      const uploaded = await uploadAudioBlob(file, file.name);
      created = await jsonPost("/voices", {
        name,
        source_type: "clone",
        languages: [language],
        engine_id: "tts.gpt-sovits",
        recipe: {
          reference_upload: uploaded.upload_id,
          reference_text: transcript,
          ...(sample ? {catalog_id: sample.id, source_url: sample.source_url, terms_url: sample.terms_url, credit: sample.credit} : {}),
        },
        rights_confirmed: true,
      });
    }
    byId("gpt-sample-name").value = "";
    byId("gpt-sample-text").value = "";
    byId("gpt-sample-file").value = "";
    byId("gpt-sample-rights").checked = false;
    showError("gpt-sample-error", "");
    await loadVoices();
    state.form.voiceId = created.id;
    await saveTtsPreference("tts.gpt-sovits", "lj1995/GPT-SoVITS", created.id);
  } catch (error) { showError("gpt-sample-error", errorText(error)); }
});

/* ── 設定：ボイス ─────────────────────────────────────────────────────── */

const VOICE_KINDS = [
  {id: "built-in", label: "voiceBuiltIn", hint: "voiceBuiltInHint"},
  {id: "design", label: "voiceDesign", hint: "voiceDesignHint"},
  {id: "clone", label: "voiceClone", hint: "voiceCloneHint"},
];

async function loadVoices() {
  try {
    const data = await api("/voices");
    state.voices = data.voices || [];
    showError("voice-error", "");
  } catch (error) {
    showError("voice-error", errorText(error));
    return;
  }
  renderVoices();
  renderStudio();
}

function renderVoices() {
  const rows = byId("voice-rows");
  if (!rows) return;
  byId("voice-empty").hidden = state.voices.length > 0;
  rows.replaceChildren(...state.voices.map((voice) => {
    const row = document.createElement("div");
    row.className = "row";
    const left = document.createElement("div");
    const title = document.createElement("div");
    title.className = "t";
    title.textContent = voice.name;
    const sub = document.createElement("div");
    sub.className = "s";
    const kind = VOICE_KINDS.find((item) => item.id === voice.source_type);
    sub.textContent = `${kind ? t(kind.label) : voice.source_type} · ${(voice.languages || []).join("/")}`;
    left.append(title, sub);
    const side = document.createElement("div");
    side.className = "row-side";
    if (voice.rights_confirmed) {
      const badge = document.createElement("span");
      badge.className = "state";
      badge.textContent = "✓";
      side.append(badge);
    }
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = t("delete");
    remove.onclick = () => confirmAction(t("deleteVoiceTitle"), t("deleteVoiceBody"), async () => {
      await api(`/voices/${encodeURIComponent(voice.id)}`, {method: "DELETE"});
      await loadVoices();
    });
    side.append(remove);
    row.append(left, side);
    return row;
  }));
}

function openVoiceDialog() {
  state.voiceKind = "built-in";
  state.voiceLanguages = ["ja", "en"];
  state.voiceReference = null;
  byId("voice-name").value = "";
  showError("voice-dialog-error", "");
  renderVoiceDialog();
  byId("voice-dialog").showModal();
}
byId("voice-add").addEventListener("click", () => openVoiceDialog());
byId("voice-cancel").addEventListener("click", () => byId("voice-dialog").close());

function renderVoiceDialog() {
  renderChips(byId("voice-kind-chips"), VOICE_KINDS, state.voiceKind, (value) => {
    state.voiceKind = value;
    renderVoiceDialog();
  });
  const kind = VOICE_KINDS.find((item) => item.id === state.voiceKind);
  byId("voice-kind-hint").textContent = t(kind.hint);
  renderChips(byId("voice-language-chips"), LANGUAGES.slice(1), state.voiceLanguages, (value) => {
    const next = new Set(state.voiceLanguages);
    next.has(value) ? next.delete(value) : next.add(value);
    state.voiceLanguages = [...next];
    if (!state.voiceLanguages.length) state.voiceLanguages = [value];
    renderVoiceDialog();
  }, {multi: true});

  const fields = byId("voice-fields");
  fields.replaceChildren();
  if (state.voiceKind === "built-in") {
    fields.append(labelled(t("voiceSpeaker"), selectNode("voice-speaker", [
      {value: "Ryan", text: "Ryan (EN)"},
      {value: "Ono_Anna", text: "Ono Anna (JA)"},
    ])));
    return;
  }
  if (state.voiceKind === "design") {
    const area = document.createElement("textarea");
    area.id = "voice-instruction";
    area.maxLength = 600;
    area.rows = 3;
    area.placeholder = state.locale === "ja"
      ? "落ち着いた低めの女性の声、少しかすれた響き"
      : "A calm, low female voice with a slightly husky tone";
    fields.append(labelled(t("voiceInstruction"), area));
    return;
  }
  const row = document.createElement("div");
  row.className = "audio-input";
  state.voiceReference = audioSlot(state.voiceReference);
  renderAudioInput(row, state.voiceReference, {
    rerender: renderVoiceDialog,
    onUploaded: transcribeVoiceReference,
  });
  const transcript = document.createElement("textarea");
  transcript.id = "voice-reference-text";
  transcript.rows = 2;
  transcript.maxLength = 2000;
  transcript.value = state.voiceReference.transcript || "";
  transcript.oninput = () => { state.voiceReference.transcript = transcript.value; };
  const rights = document.createElement("label");
  rights.className = "check";
  const check = document.createElement("input");
  check.type = "checkbox";
  check.id = "voice-rights";
  const rightsText = document.createElement("span");
  rightsText.textContent = t("voiceRights");
  rights.append(check, rightsText);
  fields.append(labelled(t("voiceReference"), row), labelled(t("voiceReferenceText"), transcript), rights);
}

/* クローンは参照音声の書き起こしを要求する（無いと x_vector_only_mode が要る）。
   利用者に打ち直させる理由はないので、取り込んだ音声をそのまま ASR に回す。 */
async function transcribeVoiceReference(slot) {
  slot.note = t("autoTranscribing");
  renderVoiceDialog();
  try {
    const created = await jsonPost("/tasks", {
      task: "speech.asr.transcribe",
      input: {upload_id: slot.uploadId},
      profile: "voice-reference",
      quality: "fast",
      content_language: "auto",
      output: {format: "wav", sample_rate: null, channels: null},
      routing: {engine: null, model: null, device: "auto"},
      seed: null,
      project_output_grant: null,
    });
    const text = await waitForTranscript(created.job_id);
    if (text) {
      slot.transcript = text;
      slot.note = t("autoTranscribed");
    } else {
      slot.note = t("autoTranscribeFailed");
    }
  } catch {
    slot.note = t("autoTranscribeFailed");
  }
  renderVoiceDialog();
}

async function waitForTranscript(jobId) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const job = await api(`/jobs/${encodeURIComponent(jobId)}`);
    if (!ACTIVE_STATES.has(job.state)) {
      return job.state === "succeeded" ? String(job.result?.text || "").trim() : "";
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  return "";
}

function labelled(text, node) {
  const label = document.createElement("label");
  label.append(document.createTextNode(text), node);
  return label;
}

function selectNode(id, options) {
  const select = document.createElement("select");
  select.id = id;
  select.replaceChildren(...options.map((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.text;
    return option;
  }));
  return select;
}

byId("voice-save").addEventListener("click", async () => {
  const name = String(byId("voice-name").value || "").trim();
  if (!name) { showError("voice-dialog-error", t("nameRequired")); return; }
  const recipe = {};
  let rights = false;
  if (state.voiceKind === "built-in") recipe.speaker = byId("voice-speaker")?.value || "Ryan";
  if (state.voiceKind === "design") recipe.design_instruction = byId("voice-instruction")?.value || "";
  if (state.voiceKind === "clone") {
    const slot = audioSlot(state.voiceReference);
    if (!slot.uploadId) { showError("voice-dialog-error", t("needAudio")); return; }
    if (!byId("voice-rights")?.checked) { showError("voice-dialog-error", t("voiceRightsRequired")); return; }
    recipe.reference_upload = slot.uploadId;
    recipe.reference_text = byId("voice-reference-text")?.value || "";
    rights = true;
  }
  try {
    await jsonPost("/voices", {
      name,
      source_type: state.voiceKind,
      languages: state.voiceLanguages,
      engine_id: state.voiceKind === "built-in" ? "tts.qwen3" : null,
      recipe,
      rights_confirmed: rights,
    });
    byId("voice-dialog").close();
    state.voiceReference = null;
    await loadVoices();
    /* 作った直後にスタジオへ戻って選び直させない。作った声を選んだ状態にする。 */
    const created = state.voices.find((voice) => voice.name === name);
    if (created) {
      state.form.voiceId = created.id;
      const select = byId("speech-voice");
      if (select) select.value = created.id;
      renderStudio();
    }
  } catch (error) {
    showError("voice-dialog-error", errorText(error));
  }
});

/* ── 設定：端末 ───────────────────────────────────────────────────────── */

byId("device-pair").addEventListener("click", async () => {
  const body = {relay_id: byId("device-relay").value || "voice"};
  const label = String(byId("device-label").value || "").trim();
  if (label) body.device_label = label;
  try {
    const created = await jsonPost("/devices/pairings", body);
    showError("device-error", "");
    const result = byId("device-result");
    result.hidden = false;
    result.textContent = JSON.stringify(created, null, 2);
  } catch (error) {
    byId("device-result").hidden = true;
    showError("device-error", error?.code === "control_deck_required" ? t("bridgeOnly") : errorText(error));
  }
});

/* ── 確認ダイアログ ───────────────────────────────────────────────────── */

function confirmAction(title, body, action) {
  byId("confirm-title").textContent = title;
  byId("confirm-body").textContent = body;
  state.confirmAction = action;
  byId("confirm-dialog").showModal();
}
byId("confirm-cancel").addEventListener("click", () => byId("confirm-dialog").close());
byId("confirm-ok").addEventListener("click", async () => {
  const action = state.confirmAction;
  byId("confirm-dialog").close();
  state.confirmAction = null;
  if (action) await action();
});

/* ── パイプライン ─────────────────────────────────────────────────────── */

/* 段が受け取れる型。サーバの _STAGE_TYPES と同じ並びで、UI 側が先に
   気付けるようにしておく。ずれたときはサーバが最終的に弾く。 */
const STAGE_INPUT_TYPE = {
  "speech.asr": "audio",
  "host.ai.text": "text",
  "speech.tts": "text",
  "audio.sfx": "text",
  "music.generate": "text",
  "audio.process": "audio",
};

/* 文章を渡したのに先頭が文字起こしだと、型が合わずに実行できない。会話は
   話しても打ってもできるべきなので、要らない段は黙って飛ばす。 */
function autoStartIndex(value) {
  const wanted = value.inputKind === "text" ? "text" : "audio";
  const index = value.stages.findIndex((stage) => STAGE_INPUT_TYPE[stage.kind] === wanted);
  return index < 0 ? 0 : index;
}

function defaultPipeline() {
  const preset = PIPELINE_PRESETS[0];
  return {
    preset: preset.id,
    inputKind: preset.input,
    stages: preset.stages.map((stage) => ({language: "auto", quality: "balanced", voice_id: "", instruction: "", ...stage})),
    startAt: "",
    stopAfter: "",
    delivery: preset.delivery,
    filename: "",
    projectGrant: "",
    audio: null,
    assetId: "",
  };
}

function renderPipeline() {
  const container = byId("pipeline-stages");
  if (!container) return;
  if (!state.pipeline) state.pipeline = defaultPipeline();
  const value = state.pipeline;

  renderChips(byId("pipeline-presets"), PIPELINE_PRESETS, value.preset, (id) => {
    const preset = PIPELINE_PRESETS.find((item) => item.id === id);
    state.pipeline = {
      ...defaultPipeline(),
      preset: preset.id,
      inputKind: preset.input,
      stages: preset.stages.map((stage) => ({language: "auto", quality: "balanced", voice_id: "", instruction: "", ...stage})),
      delivery: preset.delivery,
      audio: value.audio,
      assetId: value.assetId,
    };
    renderPipeline();
  });

  renderChips(byId("pipeline-input-kinds"), [
    {id: "text", label: "inputText"},
    {id: "audio_upload", label: "inputFile"},
    {id: "audio_asset", label: "inputAsset"},
  ], value.inputKind, (id) => { value.inputKind = id; renderPipeline(); });

  byId("pipeline-input-text").hidden = value.inputKind !== "text";
  byId("pipeline-input-file").hidden = value.inputKind !== "audio_upload";
  byId("pipeline-input-asset").hidden = value.inputKind !== "audio_asset";
  value.audio = audioSlot(value.audio);
  renderAudioInput(byId("pipeline-input-file"), value.audio, {rerender: renderPipeline});

  const assetSelect = byId("pipeline-asset");
  assetSelect.replaceChildren(...state.assets.map((asset) => {
    const option = document.createElement("option");
    option.value = asset.id;
    option.textContent = `${jobTaskLabel(assetTask(asset)) || t("audioAsset")} · ${formatSeconds(asset.duration_ms)}`;
    return option;
  }));
  assetSelect.value = value.assetId || assetSelect.value;
  assetSelect.onchange = () => { value.assetId = assetSelect.value; };

  const flow = byId("pipeline-flow");
  const ids = value.stages.map((stage) => stage.id);
  const startIndex = value.startAt ? Math.max(0, ids.indexOf(value.startAt)) : autoStartIndex(value);
  const stopIndex = value.stopAfter ? ids.indexOf(value.stopAfter) : value.stages.length - 1;
  flow.replaceChildren(...value.stages.flatMap((stage, index) => {
    const step = document.createElement("span");
    step.className = "step";
    step.dataset.active = String(index >= startIndex && index <= stopIndex);
    step.textContent = t(PIPELINE_STAGE_LABEL[stage.kind] || stage.kind);
    return index === 0 ? [step] : [Object.assign(document.createElement("span"), {textContent: "→"}), step];
  }));

  container.replaceChildren(...value.stages.map((stage, index) => {
    const card = document.createElement("div");
    card.className = "stage-card";
    card.dataset.active = String(index >= startIndex && index <= stopIndex);
    const head = document.createElement("div");
    head.className = "stage-head";
    const badge = document.createElement("span");
    badge.className = "stage-index";
    badge.textContent = String(index + 1);
    const title = document.createElement("b");
    title.textContent = t(PIPELINE_STAGE_LABEL[stage.kind] || stage.kind);
    const left = document.createElement("div");
    left.style.display = "flex";
    left.style.alignItems = "center";
    left.style.gap = "8px";
    left.append(badge, title);
    head.append(left);
    card.append(head);

    const row = document.createElement("div");
    row.className = "form-row";
    const language = selectNode(`pipeline-stage-language-${index}`, LANGUAGES.map((item) => ({
      value: item.id, text: t(item.label),
    })));
    language.value = stage.language;
    language.onchange = () => { stage.language = language.value; };
    row.append(labelled(t("contentLanguage"), language));
    const quality = selectNode(`pipeline-stage-quality-${index}`, QUALITIES.map((item) => ({
      value: item.id, text: t(item.label),
    })));
    quality.value = stage.quality;
    quality.onchange = () => { stage.quality = quality.value; };
    row.append(labelled(t("quality"), quality));
    card.append(row);

    if (stage.kind === "speech.tts") {
      const voice = selectNode(`pipeline-stage-voice-${index}`, [
        {value: "", text: t("builtInVoice")},
        ...state.voices.map((item) => ({value: item.id, text: item.name})),
      ]);
      voice.value = stage.voice_id || "";
      voice.onchange = () => { stage.voice_id = voice.value; };
      card.append(labelled(t("voice"), voice));
    }
    if (stage.kind === "host.ai.text") {
      const instruction = document.createElement("textarea");
      instruction.rows = 2;
      instruction.maxLength = 2000;
      instruction.value = stage.instruction || "";
      instruction.placeholder = state.locale === "ja"
        ? "この文章を英語に訳してください。訳文だけを返してください。"
        : "Translate this into Japanese. Return only the translation.";
      instruction.oninput = () => { stage.instruction = instruction.value; };
      card.append(labelled(t("aiInstruction"), instruction));
    }
    return card;
  }));

  for (const [id, key] of [["pipeline-start", "startAt"], ["pipeline-stop", "stopAfter"]]) {
    const select = byId(id);
    select.replaceChildren(...[{value: "", text: t("auto")}, ...value.stages.map((stage) => ({
      value: stage.id, text: t(PIPELINE_STAGE_LABEL[stage.kind] || stage.kind),
    }))].map((item) => {
      const option = document.createElement("option");
      option.value = item.value;
      option.textContent = item.text;
      return option;
    }));
    select.value = value[key] || "";
    select.onchange = () => { value[key] = select.value; renderPipeline(); };
  }

  const delivery = byId("pipeline-delivery");
  delivery.replaceChildren(...[
    {value: "text", text: t("deliveryText")},
    {value: "asset", text: t("deliveryAsset")},
    {value: "project", text: t("deliveryProject")},
  ].map((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.text;
    return option;
  }));
  delivery.value = value.delivery;
  delivery.onchange = () => { value.delivery = delivery.value; renderPipeline(); };
  byId("pipeline-project-row").hidden = value.delivery !== "project" || state.mode !== "advanced";
  byId("pipeline-project-pick").classList.toggle("filled", Boolean(value.projectGrant));
  byId("pipeline-project-pick").textContent = value.projectGrant
    ? t("projectOutputSelected") : t("chooseProjectOutput");
  byId("pipeline-project-pick").onclick = async () => {
    try {
      const grant = await callHost("host.files.export", {suggested_name: value.filename || ""});
      value.projectGrant = grant?.grant_id || grant?.export_grant_id || "";
      renderPipeline();
    } catch (error) {
      showError("pipeline-error", error?.code === "bridge_unavailable" ? t("bridgeOnly") : errorText(error));
    }
  };
  const filename = byId("pipeline-filename");
  filename.value = value.filename;
  filename.oninput = () => { value.filename = filename.value; };
}

function pipelineBody() {
  const value = state.pipeline;
  const input = {kind: value.inputKind};
  if (value.inputKind === "text") input.text = String(byId("pipeline-text").value || "").trim();
  if (value.inputKind === "audio_upload") input.upload_id = audioSlot(value.audio).uploadId;
  if (value.inputKind === "audio_asset") input.asset_id = value.assetId || byId("pipeline-asset").value;
  const body = {
    pipeline: value.preset,
    input,
    stages: value.stages.map((stage) => {
      const item = {
        id: stage.id,
        kind: stage.kind,
        language: stage.language,
        quality: stage.quality,
        routing: {engine: null, model: null, device: "auto"},
        parameters: {},
      };
      if (stage.kind === "speech.tts" && stage.voice_id) item.voice_id = stage.voice_id;
      /* runtime は system_prompt を読む。instruction のままだと指示が捨てられる。 */
      if (stage.kind === "host.ai.text" && stage.instruction) item.parameters.system_prompt = stage.instruction;
      return item;
    }),
    delivery: {mode: value.delivery, profile: "default"},
  };
  const start = value.startAt || value.stages[autoStartIndex(value)]?.id;
  if (start && start !== value.stages[0]?.id) body.start_at = start;
  if (value.stopAfter) body.stop_after = value.stopAfter;
  if (value.filename.trim()) body.delivery.filename = value.filename.trim();
  if (value.delivery === "project") body.delivery.project_output_grant = value.projectGrant || null;
  return body;
}

byId("pipeline-validate").addEventListener("click", async () => {
  showError("pipeline-error", "");
  try {
    const result = await jsonPost("/pipelines/compile", pipelineBody());
    byId("pipeline-note").textContent =
      `${t("pipelineValid")} · ${result.output_type === "text" ? t("pipelineOutputText") : t("pipelineOutputAudio")}`;
  } catch (error) {
    byId("pipeline-note").textContent = "";
    showError("pipeline-error", errorText(error));
  }
});

byId("pipeline-run").addEventListener("click", async () => {
  showError("pipeline-error", "");
  try {
    const created = await jsonPost("/pipelines", pipelineBody());
    state.activeJob = created.job_id;
    activate("studio");
    await showJob(created.job_id);
  } catch (error) {
    showError("pipeline-error", errorText(error));
  }
});

/* ── 会議 ─────────────────────────────────────────────────────────────── */
/* マイクの取得と PCM の送出はここで完結させる。edge_protocol の 18 byte
   ヘッダに合わせて 20ms ずつ送る。取れない環境では読み取り専用に落とす。 */

const MEETING_RATE = 16000;
const MEETING_FRAME_SAMPLES = 320;
const FRAME_HEADER_BYTES = 18;

/* ── 会話 ─────────────────────────────────────────────────────────────── */

/* パイプラインを毎ターン叩くと、そのたびに文字起こしと読み上げのモデルを
   読み込んで捨てる。sonic-live/2 はワーカーを会話の間ずっと常駐させたまま
   話し続けられるので、ここはそちらへ繋ぐ。 */
function defaultChat() {
  return {
    connected: false,
    connecting: false,
    mode: "idle",          // idle / listening / thinking / speaking
    autoResume: true,
    turnToken: 0,
    vad: {speechMs: 0, silenceMs: 0, heard: false},
    error: "",
    socket: null,
    turns: [],
    persona: "",
    voiceId: "",
    hostCapture: false,
    sequence: 0,
    clock: 0,
    level: 0,
  };
}

function chatState() {
  if (!state.chat) state.chat = defaultChat();
  return state.chat;
}

async function startChat() {
  const value = chatState();
  if (value.connected || value.connecting) return;
  /* 必要なのは ControlDeck の LLM であって、特定の URL ではない。橋が
     繋がっているかで判断する。 */
  if (!state.bridgePort || !state.nonce) { value.error = t("chatNeedsHost"); renderChatPanel(); return; }
  value.error = "";
  value.connecting = true;
  value.turns = [];
  renderChatPanel();

  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}${proxyRoot}/addon/v2/live/ws`;
  const socket = new WebSocket(url, [`control-deck-bridge.${state.nonce}`]);
  socket.binaryType = "arraybuffer";
  value.socket = socket;

  socket.onopen = () => {
    socket.send(JSON.stringify({
      type: "hello",
      session: {
        preset: "voice-chat",
        source_language: "auto",
        response_language: "auto",
        tts_enabled: true,
        voice_id: value.voiceId || null,
        system_prompt: (value.persona || "").trim() || t("chatPersonaDefault"),
      },
    }));
  };
  socket.onmessage = (event) => handleChatMessage(value, event);
  socket.onerror = () => { value.error = t("genericError"); renderChatPanel(); };
  socket.onclose = () => {
    value.connected = false;
    value.connecting = false;
    value.mode = "idle";
    value.socket = null;
    if (value.hostCapture) { value.hostCapture = false; void stopHostCapture(); }
    renderChatPanel();
  };
}

function handleChatMessage(value, event) {
  if (typeof event.data !== "string") { collectChatAudio(value, event.data); return; }
  let message;
  try { message = JSON.parse(event.data); } catch { return; }
  if (message.type === "tts.chunk.ready") {
    value.audioChunk = {rate: message.format?.rate || 24000, parts: []};
    return;
  }
  if (message.type === "tts.chunk.end") {
    const chunk = value.audioChunk;
    value.audioChunk = null;
    if (chunk?.parts.length) playChatAudio(pcmToWav(chunk.parts, chunk.rate));
    return;
  }
  if (message.type === "ready") {
    value.connected = true;
    value.connecting = false;
  } else if (message.type === "asr.final") {
    value.turns = [...value.turns, {role: "you", text: message.text || "", state: "final"}];
  } else if (message.type === "llm.chunk" || message.type === "reply.chunk") {
    const last = value.turns[value.turns.length - 1];
    if (last && last.role === "ai" && last.state !== "final") {
      last.text += message.text || "";
    } else {
      value.turns = [...value.turns, {role: "ai", text: message.text || "", state: "progress"}];
    }
  } else if (message.type === "llm.final" || message.type === "reply.final") {
    const last = value.turns[value.turns.length - 1];
    if (last && last.role === "ai") { last.text = message.text || last.text; last.state = "final"; }
    else value.turns = [...value.turns, {role: "ai", text: message.text || "", state: "final"}];
  } else if (message.type === "turn.complete") {
    /* 返事の音は生成しながら届くので、turn.complete の時点ではまだ鳴り
       終わっていない。鳴り終わってから聞き耳に戻さないと、自分の返事を
       自分で拾って会話が止まらなくなる。 */
    value.mode = "speaking";
    const generation = ++value.turnToken;
    chatPlayQueue = chatPlayQueue.then(() => {
      if (value.turnToken !== generation || !value.autoResume || !value.connected) {
        if (value.mode === "speaking") { value.mode = "idle"; renderChatPanel(); }
        return;
      }
      listenForSpeech();
    });
  } else if (message.type === "turn.error" || message.type === "error") {
    value.error = message.message || t("failed");
    value.mode = "idle";
  }
  renderChatPanel();
}

/* 音は WAV ではなく AudioFrame に包まれた生 PCM で届く。ヘッダを外して
   ためておき、chunk の切れ目で 1 つの WAV にしてから鳴らす。 */
function collectChatAudio(value, buffer) {
  const chunk = value.audioChunk;
  if (!chunk || !buffer || buffer.byteLength <= FRAME_HEADER_BYTES) return;
  const body = buffer.slice(FRAME_HEADER_BYTES);
  chunk.parts.push(new Int16Array(body, 0, body.byteLength >> 1));
}

/* 返事は生成しながら細切れで届く。届いた順に鳴らさないと言葉が前後するので、
   1 本の待ち行列につないで、前が鳴り終わってから次を出す。 */
let chatPlayQueue = Promise.resolve();

function playChatAudio(blob) {
  if (!blob || blob.size <= 44) return;
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  chatPlayQueue = chatPlayQueue
    .then(() => audio.play())
    .then(() => new Promise((resolve) => { audio.onended = resolve; audio.onerror = resolve; }))
    .catch(() => {
      /* 携帯は利用者の操作なしに音を出さないことがある。会話は「話す」を
         押した流れの中なので普通は通るが、断られたときは黙らせない。 */
      const value = chatState();
      value.error = t("chatPlaybackBlocked");
      renderChatPanel();
    })
    .finally(() => URL.revokeObjectURL(url));
}

/* 会話の往復。押している間だけ話す方式は確実だが、両手が要る。マイクを開いた
   まま「話し終わり」を音で見つけて自分で区切り、返事を鳴らし終えたら聞き耳に
   戻る。取り込み自体は会話の間つなぎっぱなしにする。開き直すたびに host へ
   要求が飛んで数百ミリ秒持っていかれ、往復のたびに間が空くからである。 */
const VAD_SPEECH_PEAK = 0.06;      // これを超えたら声とみなす
const VAD_HANGOVER_MS = 900;       // 声が止まってから区切るまで
const VAD_MIN_SPEECH_MS = 300;     // これ未満は物音として捨てる

function resetChatVad(value) {
  value.vad = {speechMs: 0, silenceMs: 0, heard: false};
}

/* 1 フレームぶんの音を見て、話し終わりなら true を返す。 */
function observeChatFrame(value, samples, peak) {
  const frameMs = Math.round((samples.length / HOST_CAPTURE_RATE) * 1000);
  const vad = value.vad;
  if (peak >= VAD_SPEECH_PEAK) {
    vad.speechMs += frameMs;
    vad.silenceMs = 0;
    if (vad.speechMs >= VAD_MIN_SPEECH_MS) vad.heard = true;
    return false;
  }
  vad.silenceMs += frameMs;
  return vad.heard && vad.silenceMs >= VAD_HANGOVER_MS;
}

async function startChatSession() {
  const value = chatState();
  if (value.hostCapture) return true;
  try {
    await startHostCapture((samples, peak) => {
      value.level = peak;
      if (value.mode !== "listening" || value.socket?.readyState !== WebSocket.OPEN) return;
      value.socket.send(encodeAudioFrame(value.sequence, value.clock, samples));
      value.sequence = (value.sequence + 1) >>> 0;
      value.clock = (value.clock + samples.length) >>> 0;
      if (observeChatFrame(value, samples, peak)) commitChatTurn();
    });
    value.hostCapture = true;
    return true;
  } catch (error) {
    value.error = error?.message || t("micDenied");
    renderChatPanel();
    return false;
  }
}

function listenForSpeech() {
  const value = chatState();
  if (!value.connected || value.mode === "listening") return;
  if (value.socket?.readyState !== WebSocket.OPEN) return;
  value.sequence = 0;
  value.clock = 0;
  resetChatVad(value);
  value.mode = "listening";
  value.socket.send(JSON.stringify({type: "input.start"}));
  renderChatPanel();
}

async function beginChatTurn() {
  const value = chatState();
  if (!value.connected) return;
  value.autoResume = true;
  if (!(await startChatSession())) return;
  listenForSpeech();
}

/* もう一度押されたら聞くのをやめる。会話そのものは繋いだままにして、
   次に押したときすぐ再開できるようにする。 */
function pauseChat() {
  const value = chatState();
  if (value.mode === "listening" && value.socket?.readyState === WebSocket.OPEN) {
    /* 話しかけた分は捨てずに通す。取りやめではなく、区切りである。 */
    value.socket.send(JSON.stringify({type: "input.commit"}));
    value.mode = "thinking";
  } else {
    value.mode = "idle";
  }
  value.autoResume = false;
  renderChatPanel();
}

/* 話し終わりを見つけたら、そこで区切って聞くのをやめる。返事の音を自分の
   マイクが拾って会話が自分に反応し続けるのを防ぐ。 */
function commitChatTurn() {
  const value = chatState();
  if (value.mode !== "listening") return;
  value.mode = "thinking";
  if (value.socket?.readyState === WebSocket.OPEN) {
    value.socket.send(JSON.stringify({type: "input.commit"}));
  }
  renderChatPanel();
}

function stopChat() {
  const value = chatState();
  value.mode = "idle";
  value.autoResume = false;
  if (value.hostCapture) { value.hostCapture = false; void stopHostCapture(); }
  try { value.socket?.send(JSON.stringify({type: "close"})); } catch { /* すでに閉じている */ }
  try { value.socket?.close(); } catch { /* すでに閉じている */ }
  value.connected = false;
  value.socket = null;
  renderChatPanel();
}

function renderChatPanel() {
  const panel = byId("chat-panel");
  if (!panel || state.task !== "chat") return;
  const value = chatState();
  panel.replaceChildren();

  const card = document.createElement("div");
  card.className = "panel";
  const heading = document.createElement("p");
  heading.className = "field-label";
  heading.textContent = t("chatTitle");
  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent = value.connected ? t("chatTurnHint") : t("chatHint");
  card.append(heading, hint);

  if (!value.connected) {
    const voice = selectNode("chat-voice", [
      {value: "", text: t("builtInVoice")},
      ...state.voices.map((item) => ({value: item.id, text: item.name})),
    ]);
    voice.value = value.voiceId;
    voice.onchange = () => { value.voiceId = voice.value; };
    card.append(labelled(t("chatVoice"), voice));

    const persona = document.createElement("textarea");
    persona.rows = 2;
    persona.maxLength = 2000;
    persona.value = value.persona;
    persona.placeholder = t("chatPersonaDefault");
    persona.oninput = () => { value.persona = persona.value; };
    card.append(labelled(t("chatPersona"), persona));
  }

  const action = document.createElement("button");
  action.type = "button";
  action.className = "primary";
  if (value.connecting) {
    action.textContent = t("chatConnecting");
    action.disabled = true;
  } else if (value.connected) {
    action.textContent = t("chatStop");
    action.classList.remove("primary");
    action.onclick = stopChat;
  } else {
    action.textContent = t("chatStart");
    action.onclick = () => void startChat();
  }
  card.append(action);

  if (value.connected) {
    /* 一度押せば、あとは話し終わりを見つけて自分で区切り、返事を鳴らし終えたら
       また聞き耳に戻る。もう一度押すと会話ごと止める。 */
    const talk = document.createElement("button");
    talk.type = "button";
    talk.id = "chat-talk";
    talk.className = value.mode === "listening" ? "cta-secondary recording" : "cta-secondary";
    talk.textContent = value.mode === "listening" ? t("chatTalking")
      : value.mode === "thinking" ? t("chatThinking")
      : value.mode === "speaking" ? t("chatSpeaking")
      : `\u{1F3A4} ${t("chatTalk")}`;
    talk.onclick = () => {
      if (value.mode === "idle") void beginChatTurn(); else pauseChat();
    };
    card.append(talk);
  }

  if (value.error) {
    const error = document.createElement("p");
    error.className = "error";
    error.setAttribute("role", "alert");
    error.textContent = value.error;
    card.append(error);
  }
  panel.append(card);

  const log = document.createElement("div");
  log.className = "panel";
  const logLabel = document.createElement("p");
  logLabel.className = "section-label";
  logLabel.textContent = t("chatTitle");
  log.append(logLabel);
  if (!value.turns.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = value.connected ? t("chatReady") : t("chatEmpty");
    log.append(empty);
  } else {
    const list = document.createElement("div");
    list.className = "segments";
    list.append(...value.turns.map((turn) => {
      const node = document.createElement("div");
      node.className = "segment";
      node.dataset.state = turn.state || "final";
      node.dataset.role = turn.role;
      const meta = document.createElement("div");
      meta.className = "meta";
      const who = document.createElement("span");
      who.textContent = turn.role === "you" ? t("chatYou") : t("chatReply");
      meta.append(who);
      const body = document.createElement("div");
      body.className = "src";
      body.textContent = turn.text || t("segmentWaiting");
      if (!turn.text) body.classList.add("waiting");
      node.append(meta, body);
      return node;
    }));
    log.append(list);
    requestAnimationFrame(() => { list.scrollTop = list.scrollHeight; });
  }
  panel.append(log);
}

function defaultMeeting() {
  return {
    title: state.locale === "ja" ? "打ち合わせ" : "Meeting",
    sourceLanguage: "auto",
    translate: false,
    targetLanguage: "en",
    /* 会議は「録りながら文字にして、終わりに議事録をもらう」ための画面なので、
       議事録は既定で作る。要らない人だけ外せばよい。 */
    summarize: true,
    chunkSeconds: 6,
    recording: false,
    socket: null,
    audio: null,
    stream: null,
    processor: null,
    sequence: 0,
    clock: 0,
    level: 0,
    segments: [],
    summary: "",
    meetingId: "",
    past: [],
    error: "",
  };
}

function renderMeetingPanel() {
  const panel = byId("meeting-panel");
  if (!panel || state.task !== "meeting") return;
  if (!state.meeting) state.meeting = defaultMeeting();
  const value = state.meeting;

  panel.replaceChildren();
  const card = document.createElement("div");
  card.className = "panel";

  const head = document.createElement("div");
  head.className = "live-head";
  const title = document.createElement("p");
  title.className = "field-label";
  title.textContent = t("meetingTitle");
  head.append(title);
  if (value.recording) {
    const dot = document.createElement("span");
    dot.className = "dot-live";
    const label = document.createElement("span");
    label.className = "hint";
    label.textContent = t("meetingRecording");
    head.append(dot, label);
  }
  card.append(head);

  const hint = document.createElement("p");
  hint.className = "hint";
  hint.textContent = t("meetingHint");
  card.append(hint);

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.maxLength = 200;
  nameInput.value = value.title;
  nameInput.disabled = value.recording;
  nameInput.oninput = () => { value.title = nameInput.value; };
  card.append(labelled(t("meetingTitleField"), nameInput));

  const row = document.createElement("div");
  row.className = "form-row";
  const source = selectNode("meeting-source", LANGUAGES.map((item) => ({value: item.id, text: t(item.label)})));
  source.value = value.sourceLanguage;
  source.disabled = value.recording;
  source.onchange = () => { value.sourceLanguage = source.value; };
  row.append(labelled(t("contentLanguage"), source));
  const chunk = document.createElement("input");
  chunk.type = "number";
  chunk.min = "5";
  chunk.max = "60";
  chunk.value = String(value.chunkSeconds);
  chunk.disabled = value.recording;
  chunk.onchange = () => { value.chunkSeconds = Math.min(60, Math.max(3, Number(chunk.value) || 6)); };
  row.append(labelled(t("meetingChunk"), chunk));
  card.append(row);

  /* 同時翻訳は会議中に一番触る操作なので、埋もれるチェックボックスではなく
     状態がそのまま読める切り替えにする。録音中は構成を変えられない。 */
  const translateLabel = document.createElement("p");
  translateLabel.className = "section-label";
  translateLabel.textContent = t("meetingLiveTranslate");
  const translateToggle = document.createElement("button");
  translateToggle.type = "button";
  translateToggle.className = "chip";
  translateToggle.setAttribute("aria-pressed", String(value.translate));
  translateToggle.textContent = value.translate ? t("meetingTranslateOn") : t("meetingTranslateOff");
  translateToggle.disabled = value.recording;
  translateToggle.onclick = () => { value.translate = !value.translate; renderMeetingPanel(); };
  const translateRow = document.createElement("div");
  translateRow.className = "chips";
  translateRow.append(translateToggle);
  if (value.translate) {
    for (const [id, key] of [["ja", "japanese"], ["en", "english"]]) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.setAttribute("aria-checked", String(value.targetLanguage === id));
      chip.textContent = `→ ${t(key)}`;
      chip.disabled = value.recording;
      chip.onclick = () => { value.targetLanguage = id; renderMeetingPanel(); };
      translateRow.append(chip);
    }
  }
  card.append(translateLabel, translateRow);

  const summarize = document.createElement("label");
  summarize.className = "check";
  const summarizeInput = document.createElement("input");
  summarizeInput.type = "checkbox";
  summarizeInput.checked = value.summarize;
  summarizeInput.disabled = value.recording;
  summarizeInput.onchange = () => { value.summarize = summarizeInput.checked; };
  const summarizeText = document.createElement("span");
  summarizeText.textContent = t("meetingMakeMinutes");
  summarize.append(summarizeInput, summarizeText);
  card.append(summarize);

  if (value.recording) {
    const meterLabel = document.createElement("p");
    meterLabel.className = "section-label";
    meterLabel.textContent = t("inputLevel");
    const meter = document.createElement("div");
    meter.className = "meter";
    const meterBar = document.createElement("i");
    meterBar.id = "meeting-level";
    meterBar.style.width = `${Math.round(value.level * 100)}%`;
    meter.append(meterBar);
    card.append(meterLabel, meter);
  }

  if (value.error) {
    const error = document.createElement("p");
    error.className = "error";
    error.textContent = value.error;
    card.append(error);
  }

  const action = document.createElement("button");
  action.type = "button";
  action.className = "primary";
  action.textContent = value.recording ? t("meetingStop") : t("meetingStart");
  action.onclick = () => (value.recording ? stopMeeting() : startMeeting());
  card.append(action);

  /* 読むのは書き起こしである。会議名や区切りの長さは始める前に一度触るだけ
     なので、話し始めたら文字が先に来るように並べ替える。 */
  if (value.segments.length || value.summary) {
    const live = document.createElement("div");
    live.className = "panel";
    const heading = document.createElement("p");
    heading.className = "section-label";
    heading.textContent = t("meetingTitle");
    live.append(heading);
    const list = document.createElement("div");
    list.className = "segments";
    list.append(...value.segments.map(renderSegment));
    live.append(list);
    requestAnimationFrame(() => followLatestSegment(list));
    if (value.summary) {
      const summaryLabel = document.createElement("p");
      summaryLabel.className = "section-label";
      summaryLabel.textContent = t("meetingMinutes");
      const summaryBody = document.createElement("pre");
      summaryBody.className = "transcript";
      summaryBody.textContent = value.summary;
      live.append(summaryLabel, summaryBody);
    }
    panel.append(live);
  }

  if (value.pendingMinutes && !value.summary) {
    const pending = document.createElement("p");
    pending.className = "notice";
    pending.setAttribute("role", "status");
    pending.textContent = t("meetingMinutesPending");
    panel.append(pending);
  }

  panel.append(card);

  const past = document.createElement("div");
  past.className = "panel";
  const pastLabel = document.createElement("p");
  pastLabel.className = "section-label";
  pastLabel.textContent = t("meetingPast");
  past.append(pastLabel);
  if (!value.past.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = t("meetingNoPast");
    past.append(empty);
  } else {
    const rows = document.createElement("div");
    rows.className = "rows";
    rows.append(...value.past.map((meeting) => {
      const item = document.createElement("div");
      item.className = "row";
      const left = document.createElement("div");
      const name = document.createElement("div");
      name.className = "t";
      name.textContent = meeting.title;
      const sub = document.createElement("div");
      sub.className = "s";
      sub.textContent = `${meeting.state} · ${meeting.created_at ? new Date(meeting.created_at).toLocaleString() : ""}`;
      left.append(name, sub);
      const actions = document.createElement("div");
      actions.className = "row-side";
      const open = document.createElement("button");
      open.type = "button";
      open.textContent = t("meetingTranscript");
      open.onclick = () => openMeetingTranscript(meeting.id);
      actions.append(open);
      if (meeting.summary?.markdown) {
        const minutes = document.createElement("button");
        minutes.type = "button";
        minutes.textContent = t("meetingMinutes");
        minutes.onclick = () => {
          byId("detail-facts").replaceChildren();
          byId("detail-raw").textContent = meeting.summary.markdown;
          byId("detail-dialog").showModal();
        };
        actions.append(minutes);
      }
      item.append(left, actions);
      return item;
    }));
    past.append(rows);
  }
  panel.append(past);
}

/* KasaneCore の Echo と同じ形にする。1 発言が 1 枚、上に言語と時刻と状態、
   本文の下に訳。文字が来る前の枠も潰さず、待っていることが分かるようにする。 */
const SEGMENT_FLAG = {ja: "\u{1F1EF}\u{1F1F5}", en: "\u{1F1FA}\u{1F1F8}"};

const SEGMENT_STATE_LABEL = {
  queued: "segmentQueued", progress: "segmentProgress", failed: "segmentFailed",
};

function renderSegment(segment) {
  const node = document.createElement("div");
  const phase = segment.state || "final";
  node.className = "segment";
  node.dataset.state = phase;

  const meta = document.createElement("div");
  meta.className = "meta";
  const language = segment.language || state.meeting?.sourceLanguage || "";
  const flag = document.createElement("span");
  flag.className = "flag";
  flag.textContent = SEGMENT_FLAG[language] || "\u{1F5E3}";
  const time = document.createElement("span");
  time.className = "time";
  time.textContent = `${formatClock(segment.start_ms)} – ${formatClock(segment.end_ms)}`;
  const badge = document.createElement("span");
  badge.className = "state";
  badge.textContent = SEGMENT_STATE_LABEL[phase] ? t(SEGMENT_STATE_LABEL[phase]) : "";
  meta.append(flag, time, badge);

  const source = document.createElement("div");
  source.className = "src";
  const text = segment.source_text || segment.message || "";
  if (text) {
    source.textContent = text;
  } else {
    source.textContent = t("segmentWaiting");
    source.classList.add("waiting");
  }
  node.append(meta, source);

  if (segment.translated_text) {
    const target = document.createElement("div");
    target.className = "dst";
    target.textContent = segment.translated_text;
    node.append(target);
  }
  return node;
}

/* 話している間は最新を追う。過去を読み返しているときに引き戻さないよう、
   すでに下端にいるときだけ動かす。 */
function followLatestSegment(list) {
  const previous = state.meeting?.scrollBottom;
  const atBottom = previous === undefined
    || previous <= 24
    || list.scrollHeight - list.scrollTop - list.clientHeight <= 24;
  if (atBottom) list.scrollTop = list.scrollHeight;
  list.onscroll = () => {
    if (state.meeting) {
      state.meeting.scrollBottom = list.scrollHeight - list.scrollTop - list.clientHeight;
    }
  };
}

async function loadMeetings() {
  if (!state.meeting) state.meeting = defaultMeeting();
  try {
    const data = await api("/meetings");
    state.meeting.past = data.meetings || [];
  } catch { state.meeting.past = []; }
  renderMeetingPanel();
}

async function openMeetingTranscript(id) {
  try {
    const response = await fetch(apiUrl(`/meetings/${encodeURIComponent(id)}/transcript.txt`), {
      headers: proxyRoot && state.nonce ? {"X-Control-Deck-Bridge-Session": state.nonce} : {},
      credentials: proxyRoot ? "include" : "same-origin",
    });
    const text = await response.text();
    byId("detail-facts").replaceChildren();
    byId("detail-raw").textContent = text || "";
    byId("detail-dialog").showModal();
  } catch (error) {
    state.meeting.error = errorText(error);
    renderMeetingPanel();
  }
}

function encodeAudioFrame(sequence, clock, samples) {
  const buffer = new ArrayBuffer(FRAME_HEADER_BYTES + samples.byteLength);
  const view = new DataView(buffer);
  const magic = "SFA1";
  for (let index = 0; index < 4; index += 1) view.setUint8(index, magic.charCodeAt(index));
  view.setUint8(4, 1);
  view.setUint8(5, 1);
  view.setUint8(6, 0);
  view.setUint8(7, 0);
  view.setUint32(8, sequence >>> 0, false);
  view.setUint32(12, clock >>> 0, false);
  view.setUint16(16, samples.byteLength, false);
  new Uint8Array(buffer, FRAME_HEADER_BYTES).set(new Uint8Array(samples.buffer, samples.byteOffset, samples.byteLength));
  return buffer;
}

async function startMeeting() {
  const value = state.meeting;
  value.error = "";
  value.segments = [];
  value.summary = "";
  /* ControlDeck の中ではマイクを開けない。host に開いてもらい、PCM だけ受け取る。 */
  const viaHost = hostCaptureAvailable();
  let stream = null;
  if (!viaHost) {
    if (!navigator.mediaDevices?.getUserMedia || !window.AudioContext) {
      value.error = t("meetingMicUnsupported");
      renderMeetingPanel();
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true},
      });
    } catch (error) {
      value.error = error?.name === "SecurityError" ? t("micBlockedInFrame") : t("meetingMicDenied");
      renderMeetingPanel();
      return;
    }
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}${API}/meetings/ws`;
  const socket = proxyRoot ? new WebSocket(url, [`control-deck-bridge.${state.nonce}`]) : new WebSocket(url);
  socket.binaryType = "arraybuffer";
  value.socket = socket;
  value.stream = stream;
  value.sequence = 0;
  value.clock = 0;

  socket.onopen = () => {
    socket.send(JSON.stringify({
      type: "hello",
      meeting: {
        title: value.title || "Meeting",
        source_language: value.sourceLanguage,
        target_language: value.translate ? value.targetLanguage : null,
        translate: value.translate,
        summarize: value.summarize,
        chunk_seconds: value.chunkSeconds,
        audio: {codec: "pcm_s16le", rate: MEETING_RATE, channels: 1, frame_ms: 20},
      },
    }));
  };
  socket.onmessage = (event) => {
    let message;
    try { message = JSON.parse(event.data); } catch { return; }
    if (message.type === "ready") {
      value.meetingId = message.meeting_id;
      value.recording = true;
      if (viaHost) void startMeetingHostCapture(); else startMeetingCapture(stream);
      renderMeetingPanel();
    }
    /* 区切りは 受付 → 処理中 → 確定 の順で知らせが来る。確定だけを待つと、
       話してから何秒も画面が動かない。受け付けた時点で枠を出し、同じ枠を
       書き換えていく。 */
    if (message.type?.startsWith("meeting.segment.")) {
      const phase = message.type.slice("meeting.segment.".length);
      const state_ = phase === "error" ? "failed" : phase === "final" ? "final" : phase;
      const sequence = message.sequence;
      const existing = value.segments.findIndex((item) => item.sequence === sequence);
      const merged = {
        sequence,
        start_ms: message.start_ms ?? value.segments[existing]?.start_ms,
        end_ms: message.end_ms ?? value.segments[existing]?.end_ms,
        source_text: message.source_text ?? value.segments[existing]?.source_text ?? "",
        translated_text: message.translated_text ?? value.segments[existing]?.translated_text ?? "",
        message: message.message ?? "",
        language: message.language ?? value.segments[existing]?.language,
        state: state_,
      };
      value.segments = existing < 0
        ? [...value.segments, merged]
        : value.segments.map((item, index) => (index === existing ? merged : item));
      renderMeetingPanel();
    }
    /* サーバは meeting.complete で終わりを告げ、議事録は summary.markdown に
       入っている。以前は meeting.finished を待っていたので受け取れていなかった。 */
    if (message.type === "meeting.complete") {
      value.summary = String(message.summary?.markdown || "");
      value.pendingMinutes = false;
      renderMeetingPanel();
    }
    if (message.type === "error") {
      value.error = message.message || t("genericError");
      renderMeetingPanel();
    }
  };
  socket.onerror = () => { value.error = t("genericError"); renderMeetingPanel(); };
  socket.onclose = () => { teardownMeetingCapture(); void loadMeetings(); };
}

function startMeetingCapture(stream) {
  const value = state.meeting;
  const context = new AudioContext({sampleRate: MEETING_RATE});
  value.audio = context;
  const source = context.createMediaStreamSource(stream);
  /* AudioWorklet は blob URL のモジュールを要求する。opaque origin の
     iframe では読み込めないことがあるので、どこでも動く方を選ぶ。 */
  const processor = context.createScriptProcessor(4096, 1, 1);
  value.processor = processor;
  let pending = new Float32Array(0);
  processor.onaudioprocess = (event) => {
    if (!value.recording || value.socket?.readyState !== WebSocket.OPEN) return;
    const input = event.inputBuffer.getChannelData(0);
    const merged = new Float32Array(pending.length + input.length);
    merged.set(pending, 0);
    merged.set(input, pending.length);
    let peak = 0;
    for (let index = 0; index < input.length; index += 1) peak = Math.max(peak, Math.abs(input[index]));
    value.level = peak;
    const meter = byId("meeting-level");
    if (meter) meter.style.width = `${Math.round(Math.min(1, peak * 1.6) * 100)}%`;
    let offset = 0;
    while (merged.length - offset >= MEETING_FRAME_SAMPLES) {
      const samples = new Int16Array(MEETING_FRAME_SAMPLES);
      for (let index = 0; index < MEETING_FRAME_SAMPLES; index += 1) {
        const clamped = Math.max(-1, Math.min(1, merged[offset + index]));
        samples[index] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
      }
      value.socket.send(encodeAudioFrame(value.sequence, value.clock, samples));
      value.sequence = (value.sequence + 1) >>> 0;
      value.clock = (value.clock + MEETING_FRAME_SAMPLES) >>> 0;
      offset += MEETING_FRAME_SAMPLES;
    }
    pending = merged.slice(offset);
  };
  source.connect(processor);
  /* ScriptProcessor は出力へ繋がないと呼ばれない実装がある。無音を出す。 */
  const silence = context.createGain();
  silence.gain.value = 0;
  processor.connect(silence);
  silence.connect(context.destination);
}

/* host 録音のときは frame が event で届く。socket へそのまま流す。 */
async function startMeetingHostCapture() {
  const value = state.meeting;
  try {
    await startHostCapture((samples, peak) => {
      if (!value.recording || value.socket?.readyState !== WebSocket.OPEN) return;
      value.level = peak;
      const meter = byId("meeting-level");
      if (meter) meter.style.width = `${Math.round(Math.min(1, peak * 1.6) * 100)}%`;
      value.socket.send(encodeAudioFrame(value.sequence, value.clock, samples));
      value.sequence = (value.sequence + 1) >>> 0;
      value.clock = (value.clock + samples.length) >>> 0;
    });
    value.hostCapture = true;
  } catch (error) {
    value.error = error?.message || t("meetingMicDenied");
    value.recording = false;
    try { value.socket?.close(); } catch { /* すでに閉じている */ }
    renderMeetingPanel();
  }
}

function teardownMeetingCapture() {
  const value = state.meeting;
  if (!value) return;
  if (value.hostCapture) { value.hostCapture = false; void stopHostCapture(); }
  value.recording = false;
  value.level = 0;
  try { value.processor?.disconnect(); } catch { /* すでに切れている */ }
  try { value.audio?.close(); } catch { /* すでに閉じている */ }
  for (const track of value.stream?.getTracks() || []) track.stop();
  value.processor = null;
  value.audio = null;
  value.stream = null;
  renderMeetingPanel();
}

function stopMeeting() {
  const value = state.meeting;
  if (value.socket?.readyState === WebSocket.OPEN) value.socket.send(JSON.stringify({type: "stop"}));
  /* 停止しても、まだ最後の区切りの文字起こしと議事録づくりが残っている。
     socket は meeting.complete を送ってから閉じるので、ここでは閉じない。 */
  value.pendingMinutes = value.summarize;
  teardownMeetingCapture();
}

/* ── 起動 ─────────────────────────────────────────────────────────────── */

for (const button of $$("#shell-nav button")) {
  button.addEventListener("click", () => activate(button.dataset.view));
}
byId("nav-settings").addEventListener("click", () => {
  activate(state.view === "settings" ? state.lastNonSettingsView : "settings");
});
byId("task-select").addEventListener("change", (event) => setTask(event.target.value));
byId("mode-simple").addEventListener("click", () => setMode("simple"));
byId("mode-advanced").addEventListener("click", () => setMode("advanced"));
byId("locale-toggle").addEventListener("click", () => setLocale(state.locale === "ja" ? "en" : "ja"));
for (const button of $$("[data-refresh]")) {
  button.addEventListener("click", () => void reloadAuthoritative());
}
byId("setup-plan-refresh").addEventListener("click", () => void loadPlan());

async function reloadAuthoritative() {
  const work = [loadSetup(), loadCapabilities(), loadModels(), loadTtsSettings(), loadVoices(), loadActiveJobs(), loadAssets()];
  if (state.task === "meeting") work.push(loadMeetings());
  await Promise.allSettled(work);
}

function reloadWhenReady() {
  if (!proxyRoot || state.nonce) { connect(); void reloadAuthoritative(); }
}
document.addEventListener("visibilitychange", () => { if (!document.hidden) reloadWhenReady(); });
window.addEventListener("pageshow", reloadWhenReady);
window.addEventListener("online", connect);

function boot() {
  const savedLocale = recall("locale");
  if (!state.localeFromHost && (savedLocale === "ja" || savedLocale === "en")) state.locale = savedLocale;
  setMode(recall("mode") === "advanced" ? "advanced" : "simple", {persist: false});
  const savedTask = recall("task");
  setTask(savedTask && TASKS.includes(savedTask) ? savedTask : "speech");
  applyLocale();
  activate(app().dataset.startView || "studio", {sync: false});
  if (!proxyRoot) {
    document.documentElement.dataset.bridge = "standalone";
    app().setAttribute("aria-busy", "false");
    connect();
    void reloadAuthoritative();
  }
}

/* localization.js はこの後に読み込まれる。初期描画をひと呼吸遅らせて、
   ローカライズスタジオが定義済みの状態で最初の描画に入れるようにする。 */
setTimeout(boot, 0);

Object.assign(window, {
  api, apiUrl, jsonPost, callHost, t, state, byId, $$, escapeHtml, errorText,
  showJob, showError, labelled, selectNode, renderChips, formatSeconds, LANGUAGES,
});
