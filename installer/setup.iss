; setup.iss  ─  Inno Setup インストーラ定義
; build.bat から自動実行されます。
; 手動実行: Inno Setup Compiler で setup.iss を開いてビルド

#define MyAppName    "Onga-Kun"
#define MyAppNameEn  "onga-kun"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "warasugitewara"
#define MyAppURL     "https://github.com/warasugitewara/Onga-Kun"
#define MyAppExe     "onga-kun.exe"

[Setup]
; AppId は変更しないこと（アップデート時の同一アプリ判定に使われます）
AppId={{8F4E2D1A-3B5C-4A9E-B7D0-F6E2C4A8B3D1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases

; インストール先（Program Files）
DefaultDirName={autopf}\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; 出力先
OutputDir=Output
OutputBaseFilename=onga-kun-setup-v{#MyAppVersion}

; 圧縮設定（LZMA2 最高圧縮）
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; 見た目
WizardStyle=modern
; SetupIconFile=..\assets\icon.ico  ; ← icon.ico を assets/ に追加したら有効化

; 既存バージョンの上書きインストール対応
CloseApplications=yes
CloseApplicationsFilter=*{#MyAppExe}
RestartApplications=no

; 管理者権限不要（ユーザーフォルダへのインストールも可能にする）
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Files]
; PyInstaller の出力（dist\onga-kun\*）を丸ごとコピー
Source: "..\dist\{#MyAppNameEn}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; settings.json は初回インストール時のみコピー（ユーザーの設定を上書きしない）
Source: "..\settings.json"; DestDir: "{app}"; Flags: onlyifdoesntexist

[Icons]
; スタートメニュー
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
; デスクトップ（ユーザーが選択可能）
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成する"; GroupDescription: "追加タスク:"

[Run]
; インストール完了後に起動するか確認
Filename: "{app}\{#MyAppExe}"; Description: "{#MyAppName} を今すぐ起動する"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; アンインストール時に生成ファイルも削除
Type: filesandordirs; Name: "{app}"

[Code]
// VB-Cable のインストール確認ダイアログ（警告のみ、強制はしない）
function InitializeSetup(): Boolean;
var
  Msg: String;
begin
  Result := True;
  if not RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Enum\Root\MEDIA\VBAudioVACWDM') then begin
    Msg := '{#MyAppName} はマイクへの音声ルーティングに VB-Cable を使用します。' + #13#10 +
           '' + #13#10 +
           '続行してインストールできますが、VB-Cable がないと' + #13#10 +
           'Discord 等のマイクへの出力機能は使えません。' + #13#10 + #13#10 +
           '後から https://vb-audio.com/Cable/ でインストールできます。' + #13#10 + #13#10 +
           'このままインストールを続けますか？';
    if MsgBox(Msg, mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end;
end;
