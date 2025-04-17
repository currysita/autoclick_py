import json
import os
import sys
import time
import tempfile
import shutil
import argparse
import pyautogui
import traceback

class AutomationEngine:
    def __init__(self, workflow_file):
        """
        自動化エンジンを初期化します
        
        Parameters:
        - workflow_file: ワークフローJSONファイルのパス
        """
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # ワークフローJSONを読み込む
        try:
            with open(workflow_file, 'r', encoding='utf-8') as f:
                self.workflow = json.load(f)
            print(f"ワークフロー '{self.workflow['name']}' を読み込みました")
        except Exception as e:
            print(f"ワークフローファイルの読み込みに失敗しました: {e}")
            raise
        
        # テンポラリディレクトリを作成（日本語パス問題対策）
        self.temp_dir = tempfile.mkdtemp()
        self.temp_images = {}
        
        # 画像ファイルをテンポラリディレクトリにコピー
        self._prepare_images()
        
        # タイムアウト設定
        self.global_timeout = self.workflow.get('timeout', 5)
        
        # PyAutoGUIの設定
        pyautogui.PAUSE = 3  # コマンド間の待機時間
        pyautogui.FAILSAFE = True  # 画面の左上隅にマウスを移動すると中断
    
    def _prepare_images(self):
        """ワークフローで使用される画像をテンポラリディレクトリにコピーします"""
        copied_images = set()  # 重複を避けるため
        
        for state in self.workflow.get('states', []):
            if 'image' in state and state['image'] not in copied_images:
                image_path = state['image']
                src_path = os.path.join(self.script_dir, image_path)
                
                # ディレクトリ構造を保持してコピー
                rel_dir = os.path.dirname(image_path)
                temp_dir_path = os.path.join(self.temp_dir, rel_dir)
                
                # 必要なディレクトリを作成
                if rel_dir and not os.path.exists(temp_dir_path):
                    os.makedirs(temp_dir_path, exist_ok=True)
                
                # ファイル名のみを取得
                filename = os.path.basename(image_path)
                temp_path = os.path.join(self.temp_dir, image_path)
                
                if os.path.exists(src_path):
                    # テンポラリディレクトリに画像をコピー
                    shutil.copy2(src_path, temp_path)
                    self.temp_images[image_path] = temp_path
                    copied_images.add(image_path)
                    print(f"画像 '{image_path}' をテンポラリディレクトリにコピーしました")
                else:
                    print(f"警告: 画像 '{image_path}' が見つかりません: {src_path}")
    
    def find_and_click(self, image_path, timeout=5, confidence=0.8, grayscale=True, offset_x=0, offset_y=0):
        """
        指定された画像を探し、見つかったらクリックします
        
        Parameters:
        - image_path: 画像ファイルのパス
        - timeout: タイムアウト時間（秒）
        - confidence: 画像マッチングの信頼度（OpenCVがインストールされている場合のみ）
        - grayscale: グレースケールマッチングを使用するか
        
        Returns:
        - 成功した場合はTrue
        """
        start_time = time.time()
        
        print(f"画像 '{os.path.basename(image_path)}' を探しています...")
        
        while time.time() - start_time < timeout:
            try:
                # OpenCVがインストールされているかチェック
                try:
                    import cv2
                    has_opencv = True
                except ImportError:
                    has_opencv = False
                
                # 画像を検索
                if has_opencv:
                    location = pyautogui.locateCenterOnScreen(
                        image_path, 
                        confidence=confidence, 
                        grayscale=grayscale
                    )
                else:
                    location = pyautogui.locateCenterOnScreen(
                        image_path, 
                        grayscale=grayscale
                    )
                
                # 画像が見つかった場合
                if location:
                    x, y = location
                    
                    # オフセットを適用
                    click_x = x + offset_x
                    click_y = y + offset_y
                    # print(f"画像 '{os.path.basename(image_path)}' を発見: ({x}, {y})")
                    # pyautogui.click(x, y)
                    print(f"画像 '{os.path.basename(image_path)}' を発見: ({x}, {y})")
                    if offset_x != 0 or offset_y != 0:
                        print(f"オフセット ({offset_x}, {offset_y}) を適用してクリック: ({click_x}, {click_y})")
                    pyautogui.click(click_x, click_y)

                    return True
            except Exception as e:
                print(f"画像検索エラー: {e}")
            
            # 短い待機
            time.sleep(0.2)
        
        print(f"タイムアウト: 画像 '{os.path.basename(image_path)}' が見つかりませんでした（{timeout}秒）")
        return False
    
    def run(self):
        """ワークフローを実行します"""
        if not self.workflow.get('states'):
            print("エラー: ワークフローに状態が定義されていません")
            return
        
        # 開始状態を取得
        current_state_id = 'start'
        
        while True:
            # 現在の状態を取得
            current_state = None
            for state in self.workflow['states']:
                if state['id'] == current_state_id:
                    current_state = state
                    break
            
            if not current_state:
                print(f"エラー: 状態 '{current_state_id}' が見つかりません")
                break
            
            # 終了状態かチェック
            if current_state.get('is_terminal', False):
                print(f"終了状態 '{current_state_id}' に到達しました")
                break
            
            print(f"\n--- 状態: {current_state_id} ---")
            if 'description' in current_state:
                print(f"説明: {current_state['description']}")
            
            # 画像がない場合はスキップ
            if 'image' not in current_state:
                print(f"警告: 状態 '{current_state_id}' に画像が定義されていません")
                # 次の状態へ
                if 'actions' in current_state and current_state['actions']:
                    current_state_id = current_state['actions'][0].get('next_state', 'end')
                else:
                    current_state_id = 'end'
                continue
            
            # 画像のパスを取得
            image_path = self.temp_images.get(current_state['image'])
            if not image_path:
                print(f"エラー: 画像 '{current_state['image']}' が準備されていません")
                break
            
            # 状態のタイムアウトを取得
            timeout = current_state.get('timeout', self.global_timeout)
                        # アクションからオフセット値を取得
            offset_x = 0
            offset_y = 0
            if 'actions' in current_state and current_state['actions']:
                action = current_state['actions'][0]
                offset_x = action.get('offset_x', 0)
                offset_y = action.get('offset_y', 0)
            # 画像を探してクリック
            success = self.find_and_click(image_path, timeout, offset_x=offset_x, offset_y=offset_y)
            
            # 次の状態を決定
            if success and 'actions' in current_state:
                # クリック成功時の次の状態
                action = current_state['actions'][0]  # 最初のアクションを実行
                current_state_id = action.get('next_state', 'end')
                print(f"状態を '{current_state_id}' に移行します")
            elif not success:
                if 'fallback' in current_state:
                    # 画像が見つからない場合のフォールバック
                    current_state_id = current_state['fallback']
                    print(f"フォールバック: 状態を '{current_state_id}' に移行します")
                elif 'on_timeout' in current_state:
                    # タイムアウト時の状態
                    current_state_id = current_state['on_timeout']
                    print(f"タイムアウト: 状態を '{current_state_id}' に移行します")
                else:
                    # デフォルトでは終了
                    print("次の状態が定義されていないため終了します")
                    break
    
    def cleanup(self):
        """一時ファイルをクリーンアップします"""
        try:
            shutil.rmtree(self.temp_dir)
            print("一時ディレクトリを削除しました")
        except Exception as e:
            print(f"一時ディレクトリの削除に失敗しました: {e}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='PyAutoGUI自動化ワークフロー実行ツール')
    parser.add_argument('workflow', nargs='?', default='workflows/auto_reply.json',
                      help='実行するワークフローファイルのパス（デフォルト: workflows/auto_reply.json）')
    parser.add_argument('--list', action='store_true', help='利用可能なワークフローを一覧表示')
    
    args = parser.parse_args()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # ワークフローディレクトリを確認
    workflow_dir = os.path.join(script_dir, 'workflows')
    if not os.path.exists(workflow_dir):
        os.makedirs(workflow_dir, exist_ok=True)
        print(f"ワークフローディレクトリを作成しました: {workflow_dir}")
    
    # ワークフロー一覧を表示
    if args.list:
        print("利用可能なワークフロー:")
        for root, _, files in os.walk(workflow_dir):
            for file in files:
                if file.endswith('.json'):
                    rel_path = os.path.relpath(os.path.join(root, file), script_dir)
                    print(f"- {rel_path}")
        return
    
    # ワークフローファイルのパスを絶対パスに変換
    workflow_file = args.workflow
    if not os.path.isabs(workflow_file):
        workflow_file = os.path.join(script_dir, workflow_file)
    
    if not os.path.exists(workflow_file):
        print(f"エラー: ワークフローファイル '{workflow_file}' が見つかりません")
        return
    
    try:
        print(f"ワークフロー '{workflow_file}' を実行します...")
        
        # 自動化エンジンを初期化
        engine = AutomationEngine(workflow_file)
        
        # 実行前の3秒カウントダウン
        print("3秒後に実行を開始します...")
        for i in range(3, 0, -1):
            print(f"{i}...")
            time.sleep(1)
        
        # ワークフローを実行
        engine.run()
        
        # クリーンアップ
        engine.cleanup()
        
        print("ワークフローの実行が完了しました")
        
    except KeyboardInterrupt:
        print("\n実行が中断されました")
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()