using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using Brushes = System.Windows.Media.Brushes;
using Button = System.Windows.Controls.Button;
using MessageBox = System.Windows.MessageBox;
using TextBox = System.Windows.Controls.TextBox;
using WpfApplication = System.Windows.Application;
using WpfProgressBar = System.Windows.Controls.ProgressBar;

namespace GPT2JSON.ArtSetup
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            var app = new WpfApplication();
            app.Run(new InstallerWindow());
        }
    }

    public sealed class InstallerWindow : Window
    {
        private const string AppName = "GPT2JSON";
        private const string AppVersion = "0.0.0";
        private const string Version = "v" + AppVersion;
        private readonly TextBox _dirBox;
        private readonly Button _installButton;
        private readonly WpfProgressBar _progress;
        private readonly TextBlock _status;
        private readonly Button _closeButton;
        private readonly Button _minButton;

        public InstallerWindow()
        {
            Title = AppName + " " + Version + " 安装";
            Width = 1120;
            Height = 640;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
            WindowStyle = WindowStyle.None;
            AllowsTransparency = true;
            ResizeMode = ResizeMode.NoResize;
            Background = Brushes.Transparent;
            Icon = LoadImage("GPT2JSON.Icon.png");
            SnapsToDevicePixels = true;
            UseLayoutRounding = true;
            NameScope.SetNameScope(this, new NameScope());

            var root = new Canvas();
            root.Width = 1120;
            root.Height = 640;
            Content = root;

            var shellArt = new Image
            {
                Width = 1040,
                Height = 560,
                Source = LoadImage("GPT2JSON.ShellArt.png"),
                Stretch = Stretch.Fill,
                IsHitTestVisible = false,
                Effect = new DropShadowEffect
                {
                    BlurRadius = 30,
                    ShadowDepth = 0,
                    Opacity = 0.42,
                    Color = Color.FromRgb(0, 0, 0)
                }
            };
            Canvas.SetLeft(shellArt, 40);
            Canvas.SetTop(shellArt, 40);
            root.Children.Add(shellArt);

            var shell = new Grid
            {
                Width = 1040,
                Height = 560,
                Clip = ShellSurfaceGeometry(),
                Background = Brushes.Transparent
            };
            Canvas.SetLeft(shell, 40);
            Canvas.SetTop(shell, 40);
            root.Children.Add(shell);
            shell.MouseLeftButtonDown += delegate(object sender, MouseButtonEventArgs args)
            {
                if (args.ChangedButton == MouseButton.Left)
                {
                    try { DragMove(); } catch { }
                }
            };

            AddBrandLabels(shell);

            AddInstallerControls(shell);

            _dirBox = FindName("InstallPathBox") as TextBox;
            _installButton = FindName("InstallButton") as Button;
            _progress = FindName("InstallProgress") as WpfProgressBar;
            _status = FindName("StatusText") as TextBlock;
            _closeButton = FindName("CloseButton") as Button;
            _minButton = FindName("MinButton") as Button;

            if (_dirBox != null)
                _dirBox.Text = EnsureAppInstallPath(DefaultInstallPath());
            if (_installButton != null)
                _installButton.Click += async delegate { await InstallAsync(); };
            if (_closeButton != null)
                _closeButton.Click += delegate { Close(); };
            if (_minButton != null)
                _minButton.Click += delegate { WindowState = WindowState.Minimized; };
        }

        private Geometry OuterShellGeometry()
        {
            // Visible window silhouette, in the 1040x560 local coordinate system.
            // The shape is planned first, then the panels are placed inside its safe zone:
            // - a swollen left brand island;
            // - a closed transparent "void lagoon" near the top right;
            // - a floating lower wave instead of a rectangular installer base.
            return Geometry.Parse(
                "M96,7 " +
                "C53,0 23,28 17,78 " +
                "C10,132 48,164 29,225 " +
                "C12,292 -4,338 34,397 " +
                "C72,456 34,504 82,535 " +
                "C130,568 202,548 274,550 " +
                "C370,554 446,528 514,510 " +
                "C612,485 704,517 802,544 " +
                "L970,544 " +
                "C1018,544 1040,514 1040,466 " +
                "L1040,84 " +
                "C1040,34 1008,8 958,8 " +
                "L790,8 " +
                "C712,8 662,48 560,30 " +
                "C500,19 453,18 382,44 " +
                "C328,66 280,48 224,24 " +
                "C178,8 143,15 96,7 Z");
        }

        private Geometry VoidHoleGeometry()
        {
            return Geometry.Parse(
                "M665,82 " +
                "C670,48 710,25 763,30 " +
                "C812,35 842,62 838,96 " +
                "C834,132 788,151 735,146 " +
                "C690,142 662,116 665,82 Z");
        }

        private Geometry ShellSurfaceGeometry()
        {
            return new CombinedGeometry(GeometryCombineMode.Exclude, OuterShellGeometry(), VoidHoleGeometry());
        }

        private void AddBrandLabels(Grid shell)
        {
            var title = new TextBlock
            {
                Text = "GPT2JSON",
                Foreground = Brushes.White,
                FontSize = 38,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(95, 306, 0, 0),
                Effect = new DropShadowEffect { BlurRadius = 18, ShadowDepth = 0, Color = Color.FromRgb(35, 162, 255), Opacity = 0.28 }
            };
            shell.Children.Add(title);

            var sub = new TextBlock
            {
                Text = "Sub2API / CPA JSON 导出工具",
                Foreground = new SolidColorBrush(Color.FromRgb(184, 205, 236)),
                FontSize = 14,
                Margin = new Thickness(103, 354, 0, 0)
            };
            shell.Children.Add(sub);

            var version = new Border
            {
                CornerRadius = new CornerRadius(12),
                Background = new SolidColorBrush(Color.FromArgb(45, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(80, 255, 255, 255)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(12, 5, 12, 5),
                HorizontalAlignment = System.Windows.HorizontalAlignment.Left,
                VerticalAlignment = System.Windows.VerticalAlignment.Bottom,
                Margin = new Thickness(114, 0, 0, 52),
                Child = new TextBlock
                {
                    Text = Version,
                    Foreground = new SolidColorBrush(Color.FromRgb(210, 225, 255)),
                    FontSize = 13,
                    FontWeight = FontWeights.SemiBold
                }
            };
            shell.Children.Add(version);
        }

        private void AddInstallerControls(Grid shell)
        {
            var overlay = new Canvas { Width = 1040, Height = 560 };
            shell.Children.Add(overlay);

            var buttons = new StackPanel { Orientation = System.Windows.Controls.Orientation.Horizontal };
            RegisterName("MinButton", WindowButton("—"));
            RegisterName("CloseButton", WindowButton("×"));
            buttons.Children.Add((Button)FindName("MinButton"));
            buttons.Children.Add((Button)FindName("CloseButton"));
            Canvas.SetLeft(buttons, 848);
            Canvas.SetTop(buttons, 82);
            overlay.Children.Add(buttons);

            var title = new TextBlock
            {
                Text = "安装",
                Foreground = Brushes.White,
                FontSize = 43,
                FontWeight = FontWeights.Bold,
                Effect = new DropShadowEffect { BlurRadius = 18, ShadowDepth = 0, Color = Color.FromRgb(43, 137, 255), Opacity = 0.18 }
            };
            Canvas.SetLeft(title, 410);
            Canvas.SetTop(title, 154);
            overlay.Children.Add(title);

            var features = new WrapPanel();
            features.Children.Add(FeaturePill("◇", "协议优先"));
            features.Children.Add(FeaturePill("▱", "批量导出"));
            features.Children.Add(FeaturePill("↯", "本地处理"));
            Canvas.SetLeft(features, 410);
            Canvas.SetTop(features, 224);
            overlay.Children.Add(features);

            var label = new TextBlock
            {
                Text = "安装位置",
                Foreground = new SolidColorBrush(Color.FromRgb(231, 240, 255)),
                FontSize = 15,
                FontWeight = FontWeights.SemiBold
            };
            Canvas.SetLeft(label, 410);
            Canvas.SetTop(label, 292);
            overlay.Children.Add(label);

            var pathBorder = new Border
            {
                Width = 568,
                Height = 58,
                CornerRadius = new CornerRadius(18),
                Background = new SolidColorBrush(Color.FromArgb(62, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(95, 142, 195, 255)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(18, 0, 10, 0)
            };
            var pathGrid = new Grid();
            pathGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(30) });
            pathGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            pathGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(96) });
            var folderIcon = new TextBlock
            {
                Text = "\uE8B7",
                FontFamily = new FontFamily("Segoe MDL2 Assets"),
                Foreground = new SolidColorBrush(Color.FromRgb(179, 204, 238)),
                FontSize = 18,
                VerticalAlignment = System.Windows.VerticalAlignment.Center,
                HorizontalAlignment = System.Windows.HorizontalAlignment.Left
            };
            pathGrid.Children.Add(folderIcon);
            var box = new TextBox
            {
                Name = "InstallPathBox",
                Foreground = new SolidColorBrush(Color.FromRgb(225, 238, 255)),
                Background = Brushes.Transparent,
                BorderThickness = new Thickness(0),
                FontSize = 15,
                VerticalContentAlignment = System.Windows.VerticalAlignment.Center,
                CaretBrush = Brushes.White
            };
            RegisterName(box.Name, box);
            Grid.SetColumn(box, 1);
            pathGrid.Children.Add(box);
            var browse = new Button
            {
                Content = "浏览",
                Height = 40,
                Margin = new Thickness(10, 8, 0, 8),
                Background = new SolidColorBrush(Color.FromArgb(55, 96, 165, 255)),
                Foreground = Brushes.White,
                BorderBrush = new SolidColorBrush(Color.FromArgb(100, 160, 205, 255)),
                Style = RoundedButtonStyle(12)
            };
            browse.Click += BrowsePath;
            Grid.SetColumn(browse, 2);
            pathGrid.Children.Add(browse);
            pathBorder.Child = pathGrid;
            Canvas.SetLeft(pathBorder, 410);
            Canvas.SetTop(pathBorder, 326);
            overlay.Children.Add(pathBorder);

            var progress = new WpfProgressBar
            {
                Name = "InstallProgress",
                Width = 568,
                Height = 5,
                Minimum = 0,
                Maximum = 100,
                Value = 0,
                Foreground = new SolidColorBrush(Color.FromRgb(54, 210, 255)),
                Background = new SolidColorBrush(Color.FromArgb(28, 255, 255, 255)),
                BorderThickness = new Thickness(0)
            };
            RegisterName(progress.Name, progress);
            Canvas.SetLeft(progress, 410);
            Canvas.SetTop(progress, 397);
            overlay.Children.Add(progress);

            var status = new TextBlock
            {
                Name = "StatusText",
                Text = "准备就绪：选择目录后即可开始安装。",
                Foreground = new SolidColorBrush(Color.FromRgb(137, 158, 196)),
                FontSize = 12
            };
            RegisterName(status.Name, status);
            Canvas.SetLeft(status, 412);
            Canvas.SetTop(status, 412);
            overlay.Children.Add(status);

            var install = new Button
            {
                Name = "InstallButton",
                Content = "↓  开始安装",
                Width = 172,
                Height = 54,
                FontSize = 17,
                FontWeight = FontWeights.Bold,
                Foreground = Brushes.White,
                Background = new LinearGradientBrush(Color.FromRgb(27, 181, 255), Color.FromRgb(176, 69, 255), 0),
                BorderBrush = new SolidColorBrush(Color.FromArgb(135, 202, 232, 255)),
                Style = RoundedButtonStyle(18)
            };
            RegisterName(install.Name, install);
            Canvas.SetLeft(install, 655);
            Canvas.SetTop(install, 434);
            overlay.Children.Add(install);

            var cancel = new Button
            {
                Content = "取消",
                Width = 132,
                Height = 54,
                FontSize = 15,
                Foreground = new SolidColorBrush(Color.FromRgb(218, 230, 255)),
                Background = new SolidColorBrush(Color.FromArgb(28, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(86, 163, 190, 255)),
                Style = RoundedButtonStyle(18)
            };
            cancel.Click += delegate { Close(); };
            Canvas.SetLeft(cancel, 850);
            Canvas.SetTop(cancel, 434);
            overlay.Children.Add(cancel);
        }
        private Border FeaturePill(string icon, string text)
        {
            var stack = new StackPanel { Orientation = System.Windows.Controls.Orientation.Horizontal };
            stack.Children.Add(new TextBlock
            {
                Text = icon,
                Foreground = new SolidColorBrush(Color.FromRgb(96, 186, 255)),
                FontSize = 15,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 0, 8, 0),
                VerticalAlignment = System.Windows.VerticalAlignment.Center
            });
            stack.Children.Add(new TextBlock
            {
                Text = text,
                Foreground = new SolidColorBrush(Color.FromRgb(220, 233, 255)),
                FontSize = 13,
                FontWeight = FontWeights.SemiBold,
                VerticalAlignment = System.Windows.VerticalAlignment.Center
            });
            return new Border
            {
                CornerRadius = new CornerRadius(14),
                Padding = new Thickness(13, 7, 13, 7),
                Margin = new Thickness(0, 0, 10, 8),
                Background = new LinearGradientBrush(Color.FromArgb(42, 255, 255, 255), Color.FromArgb(24, 107, 155, 255), 0),
                BorderBrush = new SolidColorBrush(Color.FromArgb(70, 130, 204, 255)),
                BorderThickness = new Thickness(1),
                Child = stack
            };
        }
        private Button WindowButton(string text)
        {
            return new Button
            {
                Content = text,
                Width = 42,
                Height = 34,
                Margin = new Thickness(7, 0, 0, 0),
                Foreground = new SolidColorBrush(Color.FromRgb(217, 229, 255)),
                Background = new SolidColorBrush(Color.FromArgb(32, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(45, 255, 255, 255)),
                FontSize = text == "×" ? 20 : 15,
                Style = RoundedButtonStyle(17)
            };
        }

        internal static Style RoundedButtonStyle(double radius)
        {
            var style = new Style(typeof(Button));
            var border = new FrameworkElementFactory(typeof(Border));
            border.SetValue(Border.CornerRadiusProperty, new CornerRadius(radius));
            border.SetValue(Border.BackgroundProperty, new TemplateBindingExtension(Button.BackgroundProperty));
            border.SetValue(Border.BorderBrushProperty, new TemplateBindingExtension(Button.BorderBrushProperty));
            border.SetValue(Border.BorderThicknessProperty, new TemplateBindingExtension(Button.BorderThicknessProperty));
            var content = new FrameworkElementFactory(typeof(ContentPresenter));
            content.SetValue(ContentPresenter.HorizontalAlignmentProperty, System.Windows.HorizontalAlignment.Center);
            content.SetValue(ContentPresenter.VerticalAlignmentProperty, System.Windows.VerticalAlignment.Center);
            border.AppendChild(content);
            var template = new ControlTemplate(typeof(Button));
            template.VisualTree = border;
            style.Setters.Add(new Setter(Button.TemplateProperty, template));
            style.Setters.Add(new Setter(Button.CursorProperty, System.Windows.Input.Cursors.Hand));
            style.Setters.Add(new Setter(Button.PaddingProperty, new Thickness(10, 0, 10, 0)));
            return style;
        }

        private void BrowsePath(object sender, RoutedEventArgs e)
        {
            var dlg = new InstallDirectoryDialog(
                _dirBox != null ? _dirBox.Text : DefaultInstallPath(),
                DefaultInstallPath())
            {
                Owner = this
            };
            if (dlg.ShowDialog() == true && _dirBox != null)
                _dirBox.Text = EnsureAppInstallPath(dlg.SelectedPath);
        }

        private static string DefaultInstallPath()
        {
            return System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "GPT2JSON");
        }

        private static string EnsureAppInstallPath(string selectedPath)
        {
            if (string.IsNullOrWhiteSpace(selectedPath)) return DefaultInstallPath();

            string normalized;
            try
            {
                normalized = System.IO.Path.GetFullPath(Environment.ExpandEnvironmentVariables(selectedPath.Trim().Trim('"')));
            }
            catch
            {
                normalized = selectedPath.Trim().Trim('"');
            }

            string root = System.IO.Path.GetPathRoot(normalized);
            if (!string.IsNullOrEmpty(root) && string.Equals(normalized, root, StringComparison.OrdinalIgnoreCase))
                return System.IO.Path.Combine(root, AppName);

            normalized = normalized.TrimEnd(System.IO.Path.DirectorySeparatorChar, System.IO.Path.AltDirectorySeparatorChar);
            string leaf = System.IO.Path.GetFileName(normalized);
            if (string.Equals(leaf, AppName, StringComparison.OrdinalIgnoreCase))
                return normalized;

            return System.IO.Path.Combine(normalized, AppName);
        }

        private async Task InstallAsync()
        {
            if (_dirBox == null || string.IsNullOrWhiteSpace(_dirBox.Text))
            {
                MessageBox.Show("请先选择安装目录。", AppName, MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            string installDir = EnsureAppInstallPath(_dirBox.Text);
            _dirBox.Text = installDir;

            SetBusy(true, "正在释放安装核心…", 18);
            try
            {
                string installerPath = ExtractInstaller();
                Directory.CreateDirectory(installDir);
                SetBusy(true, "安装核心已就绪，正在写入文件…", 42);
                int code = await Task.Run(delegate
                {
                    var psi = new ProcessStartInfo
                    {
                        FileName = installerPath,
                        Arguments = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=\"" + installDir + "\"",
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    var p = Process.Start(psi);
                    p.WaitForExit();
                    return p.ExitCode;
                });

                if (code != 0)
                    throw new InvalidOperationException("安装核心返回错误码：" + code);

                SetBusy(false, "安装完成：GPT2JSON 已准备好。", 100);
                TryLaunchInstalledApp();
            }
            catch (Exception ex)
            {
                SetBusy(false, "安装失败：" + ex.Message, 0);
                MessageBox.Show(ex.Message, AppName + " 安装失败", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void SetBusy(bool busy, string text, double progress)
        {
            if (_installButton != null) _installButton.IsEnabled = !busy;
            if (_dirBox != null) _dirBox.IsEnabled = !busy;
            if (_status != null) _status.Text = text;
            if (_progress != null) _progress.Value = progress;
        }

        private string ExtractInstaller()
        {
            string dir = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "GPT2JSON-ArtSetup", Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);
            string path = System.IO.Path.Combine(dir, "GPT2JSON-Setup-" + Version + ".exe");
            using (var input = Assembly.GetExecutingAssembly().GetManifestResourceStream("GPT2JSON.Setup.exe"))
            {
                if (input == null) throw new FileNotFoundException("未找到内嵌安装核心。", "GPT2JSON.Setup.exe");
                using (var output = File.Create(path))
                {
                    input.CopyTo(output);
                }
            }
            return path;
        }

        private void TryLaunchInstalledApp()
        {
            try
            {
                string exe = System.IO.Path.Combine(_dirBox.Text, "GPT2JSON.exe");
                if (File.Exists(exe))
                    Process.Start(new ProcessStartInfo { FileName = exe, UseShellExecute = true });
            }
            catch { }
        }

        private BitmapImage LoadImage(string resourceName)
        {
            using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(resourceName))
            {
                if (stream == null) return null;
                var memory = new MemoryStream();
                stream.CopyTo(memory);
                memory.Position = 0;
                var image = new BitmapImage();
                image.BeginInit();
                image.CacheOption = BitmapCacheOption.OnLoad;
                image.StreamSource = memory;
                image.EndInit();
                image.Freeze();
                return image;
            }
        }
    }

    internal sealed class InstallDirectoryDialog : Window
    {
        private readonly string _defaultPath;
        private readonly TreeView _folderTree;
        private readonly TextBox _folderBox;
        private readonly TextBlock _message;

        public string SelectedPath { get; private set; }

        public InstallDirectoryDialog(string initialPath, string defaultPath)
        {
            _defaultPath = NormalizePath(defaultPath);
            SelectedPath = NormalizePath(string.IsNullOrWhiteSpace(initialPath) ? _defaultPath : initialPath);

            Title = "浏览文件夹";
            Width = 612;
            Height = 510;
            WindowStartupLocation = WindowStartupLocation.CenterOwner;
            WindowStyle = WindowStyle.None;
            AllowsTransparency = true;
            ResizeMode = ResizeMode.NoResize;
            Background = Brushes.Transparent;
            ShowInTaskbar = false;
            SnapsToDevicePixels = true;
            UseLayoutRounding = true;

            var root = new Grid();
            Content = root;

            var glowBrush = new RadialGradientBrush();
            glowBrush.GradientStops.Add(new GradientStop(Color.FromArgb(95, 58, 194, 255), 0));
            glowBrush.GradientStops.Add(new GradientStop(Color.FromArgb(18, 146, 74, 255), 0.65));
            glowBrush.GradientStops.Add(new GradientStop(Color.FromArgb(0, 0, 0, 0), 1));
            var glow = new System.Windows.Shapes.Ellipse
            {
                Width = 360,
                Height = 230,
                Fill = glowBrush,
                HorizontalAlignment = System.Windows.HorizontalAlignment.Left,
                VerticalAlignment = System.Windows.VerticalAlignment.Top,
                Margin = new Thickness(-58, -70, 0, 0),
                IsHitTestVisible = false
            };
            root.Children.Add(glow);

            var cardBrush = new LinearGradientBrush();
            cardBrush.StartPoint = new Point(0, 0);
            cardBrush.EndPoint = new Point(1, 1);
            cardBrush.GradientStops.Add(new GradientStop(Color.FromRgb(17, 28, 62), 0));
            cardBrush.GradientStops.Add(new GradientStop(Color.FromRgb(24, 34, 78), 0.55));
            cardBrush.GradientStops.Add(new GradientStop(Color.FromRgb(41, 31, 82), 1));

            var card = new Border
            {
                Width = 560,
                Height = 446,
                CornerRadius = new CornerRadius(24),
                Background = cardBrush,
                BorderBrush = new LinearGradientBrush(Color.FromArgb(130, 92, 211, 255), Color.FromArgb(105, 185, 97, 255), 0),
                BorderThickness = new Thickness(1),
                HorizontalAlignment = System.Windows.HorizontalAlignment.Center,
                VerticalAlignment = System.Windows.VerticalAlignment.Center,
                Effect = new DropShadowEffect
                {
                    BlurRadius = 30,
                    ShadowDepth = 0,
                    Opacity = 0.42,
                    Color = Color.FromRgb(0, 0, 0)
                }
            };
            root.Children.Add(card);

            var panel = new Canvas { Width = 560, Height = 446 };
            card.Child = panel;

            var dragZone = new Border
            {
                Width = 560,
                Height = 50,
                Background = Brushes.Transparent
            };
            dragZone.MouseLeftButtonDown += delegate(object sender, MouseButtonEventArgs args)
            {
                if (args.ChangedButton == MouseButton.Left)
                {
                    try { DragMove(); } catch { }
                }
            };
            panel.Children.Add(dragZone);

            var header = new TextBlock
            {
                Text = "浏览文件夹",
                Foreground = Brushes.White,
                FontSize = 18,
                FontWeight = FontWeights.SemiBold
            };
            Canvas.SetLeft(header, 24);
            Canvas.SetTop(header, 18);
            panel.Children.Add(header);

            var close = new Button
            {
                Content = "×",
                Width = 34,
                Height = 28,
                FontSize = 17,
                Foreground = new SolidColorBrush(Color.FromRgb(222, 232, 255)),
                Background = new SolidColorBrush(Color.FromArgb(30, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(48, 255, 255, 255)),
                Style = InstallerWindow.RoundedButtonStyle(14)
            };
            close.Click += delegate { DialogResult = false; Close(); };
            Canvas.SetLeft(close, 506);
            Canvas.SetTop(close, 16);
            panel.Children.Add(close);

            var desc = new TextBlock
            {
                Text = "选择 GPT2JSON 安装目录",
                Foreground = new SolidColorBrush(Color.FromRgb(222, 234, 255)),
                FontSize = 13
            };
            Canvas.SetLeft(desc, 26);
            Canvas.SetTop(desc, 62);
            panel.Children.Add(desc);

            var treeBorder = new Border
            {
                Width = 508,
                Height = 248,
                CornerRadius = new CornerRadius(10),
                Background = new SolidColorBrush(Color.FromArgb(230, 11, 18, 42)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(92, 118, 164, 225)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(6)
            };
            _folderTree = new TreeView
            {
                Background = Brushes.Transparent,
                BorderThickness = new Thickness(0),
                Foreground = new SolidColorBrush(Color.FromRgb(226, 238, 255)),
                FontSize = 13
            };
            _folderTree.SelectedItemChanged += delegate { SyncSelectedTreePath(); };
            treeBorder.Child = _folderTree;
            Canvas.SetLeft(treeBorder, 26);
            Canvas.SetTop(treeBorder, 86);
            panel.Children.Add(treeBorder);

            var folderLabel = new TextBlock
            {
                Text = "文件夹(&F):",
                Foreground = new SolidColorBrush(Color.FromRgb(222, 234, 255)),
                FontSize = 12,
                VerticalAlignment = System.Windows.VerticalAlignment.Center
            };
            Canvas.SetLeft(folderLabel, 26);
            Canvas.SetTop(folderLabel, 352);
            panel.Children.Add(folderLabel);

            var inputBorder = new Border
            {
                Width = 408,
                Height = 34,
                CornerRadius = new CornerRadius(8),
                Background = new SolidColorBrush(Color.FromArgb(48, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(85, 130, 194, 255)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(10, 0, 10, 0)
            };
            _folderBox = new TextBox
            {
                Text = SelectedPath,
                Foreground = new SolidColorBrush(Color.FromRgb(232, 243, 255)),
                Background = Brushes.Transparent,
                BorderThickness = new Thickness(0),
                FontSize = 13,
                VerticalContentAlignment = System.Windows.VerticalAlignment.Center,
                CaretBrush = Brushes.White
            };
            inputBorder.Child = _folderBox;
            Canvas.SetLeft(inputBorder, 126);
            Canvas.SetTop(inputBorder, 345);
            panel.Children.Add(inputBorder);

            _message = new TextBlock
            {
                Text = string.Empty,
                Foreground = new SolidColorBrush(Color.FromRgb(151, 178, 222)),
                FontSize = 11
            };
            Canvas.SetLeft(_message, 126);
            Canvas.SetTop(_message, 383);
            panel.Children.Add(_message);

            var newFolder = new Button
            {
                Content = "新建文件夹(&M)",
                Width = 124,
                Height = 34,
                FontSize = 12,
                Foreground = new SolidColorBrush(Color.FromRgb(222, 234, 255)),
                Background = new SolidColorBrush(Color.FromArgb(32, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(70, 133, 198, 255)),
                Style = InstallerWindow.RoundedButtonStyle(8)
            };
            newFolder.Click += delegate { CreateFolderUnderCurrent(); };
            Canvas.SetLeft(newFolder, 26);
            Canvas.SetTop(newFolder, 398);
            panel.Children.Add(newFolder);

            var ok = new Button
            {
                Content = "确定",
                Width = 86,
                Height = 34,
                FontSize = 13,
                FontWeight = FontWeights.SemiBold,
                Foreground = Brushes.White,
                Background = new LinearGradientBrush(Color.FromRgb(31, 178, 255), Color.FromRgb(166, 74, 255), 0),
                BorderBrush = new SolidColorBrush(Color.FromArgb(120, 210, 235, 255)),
                Style = InstallerWindow.RoundedButtonStyle(8)
            };
            ok.Click += delegate { UseCurrentPath(); };
            Canvas.SetLeft(ok, 352);
            Canvas.SetTop(ok, 398);
            panel.Children.Add(ok);

            var cancel = new Button
            {
                Content = "取消",
                Width = 86,
                Height = 34,
                FontSize = 13,
                Foreground = new SolidColorBrush(Color.FromRgb(218, 230, 255)),
                Background = new SolidColorBrush(Color.FromArgb(28, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(76, 163, 190, 255)),
                Style = InstallerWindow.RoundedButtonStyle(8)
            };
            cancel.Click += delegate { DialogResult = false; Close(); };
            Canvas.SetLeft(cancel, 448);
            Canvas.SetTop(cancel, 398);
            panel.Children.Add(cancel);

            Loaded += delegate
            {
                PopulateTree();
                _folderBox.Focus();
                _folderBox.CaretIndex = _folderBox.Text.Length;
            };
        }

        private void PopulateTree()
        {
            _folderTree.Items.Clear();

            AddRootFolder("桌面", Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory));
            AddRootFolder("文档", Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments));
            AddRootFolder(Environment.UserName, Environment.GetFolderPath(Environment.SpecialFolder.UserProfile));

            var thisPc = new TreeViewItem
            {
                Header = BuildHeader("\uE80F", "此电脑"),
                Foreground = new SolidColorBrush(Color.FromRgb(226, 238, 255)),
                IsExpanded = true
            };
            _folderTree.Items.Add(thisPc);

            foreach (var drive in DriveInfo.GetDrives())
            {
                string driveName = drive.Name.TrimEnd('\\');
                string label = "本地磁盘 (" + driveName + ")";
                try
                {
                    if (!string.IsNullOrWhiteSpace(drive.VolumeLabel))
                        label = drive.VolumeLabel + " (" + driveName + ")";
                }
                catch { }
                var item = CreateFolderItem(label, drive.RootDirectory.FullName, true);
                thisPc.Items.Add(item);
            }
        }

        private void AddRootFolder(string label, string path)
        {
            if (string.IsNullOrWhiteSpace(path) || !Directory.Exists(path)) return;
            _folderTree.Items.Add(CreateFolderItem(label, path, true));
        }

        private TreeViewItem CreateFolderItem(string label, string path, bool lazy)
        {
            var item = new TreeViewItem
            {
                Header = BuildHeader("\uE8B7", label),
                Tag = path,
                Foreground = new SolidColorBrush(Color.FromRgb(226, 238, 255)),
                Padding = new Thickness(2)
            };
            if (lazy) item.Items.Add(new TreeViewItem { Header = "正在加载..." });
            item.Expanded += delegate { LoadChildren(item); };
            return item;
        }

        private StackPanel BuildHeader(string icon, string label)
        {
            var stack = new StackPanel { Orientation = System.Windows.Controls.Orientation.Horizontal };
            stack.Children.Add(new TextBlock
            {
                Text = icon,
                FontFamily = new FontFamily("Segoe MDL2 Assets"),
                Foreground = new SolidColorBrush(Color.FromRgb(118, 203, 255)),
                FontSize = 14,
                Margin = new Thickness(0, 0, 8, 0),
                VerticalAlignment = System.Windows.VerticalAlignment.Center
            });
            stack.Children.Add(new TextBlock
            {
                Text = label,
                Foreground = new SolidColorBrush(Color.FromRgb(226, 238, 255)),
                FontSize = 13,
                VerticalAlignment = System.Windows.VerticalAlignment.Center
            });
            return stack;
        }

        private void LoadChildren(TreeViewItem item)
        {
            if (item.Tag == null) return;
            if (item.Items.Count != 1 || !IsPlaceholder(item.Items[0])) return;

            item.Items.Clear();
            string path = item.Tag as string;
            if (string.IsNullOrWhiteSpace(path)) return;

            try
            {
                string[] directories = Directory.GetDirectories(path);
                Array.Sort(directories, StringComparer.CurrentCultureIgnoreCase);
                foreach (string dir in directories)
                {
                    string name = System.IO.Path.GetFileName(dir);
                    if (string.IsNullOrEmpty(name)) name = dir;
                    item.Items.Add(CreateFolderItem(name, dir, HasSubDirectory(dir)));
                }
            }
            catch (Exception ex)
            {
                _message.Text = "无法读取该文件夹：" + ex.Message;
            }
        }

        private static bool IsPlaceholder(object item)
        {
            var treeItem = item as TreeViewItem;
            return treeItem != null && treeItem.Tag == null;
        }

        private static bool HasSubDirectory(string path)
        {
            try
            {
                using (var enumerator = Directory.EnumerateDirectories(path).GetEnumerator())
                {
                    return enumerator.MoveNext();
                }
            }
            catch
            {
                return false;
            }
        }

        private void SyncSelectedTreePath()
        {
            var item = _folderTree.SelectedItem as TreeViewItem;
            if (item == null || item.Tag == null) return;
            string path = item.Tag as string;
            if (!string.IsNullOrWhiteSpace(path))
            {
                _folderBox.Text = path;
                _message.Text = string.Empty;
            }
        }

        private void CreateFolderUnderCurrent()
        {
            try
            {
                string baseDir = FindExistingDirectory(_folderBox.Text);
                if (string.IsNullOrEmpty(baseDir)) baseDir = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);

                string candidate = System.IO.Path.Combine(baseDir, "新建文件夹");
                int index = 2;
                while (Directory.Exists(candidate))
                {
                    candidate = System.IO.Path.Combine(baseDir, "新建文件夹 (" + index.ToString() + ")");
                    index++;
                }

                Directory.CreateDirectory(candidate);
                _folderBox.Text = candidate;
                _message.Text = "已创建文件夹。";
                PopulateTree();
            }
            catch (Exception ex)
            {
                _message.Text = "新建文件夹失败：" + ex.Message;
            }
        }

        private void UseCurrentPath()
        {
            string value = NormalizePath(_folderBox.Text);
            if (string.IsNullOrWhiteSpace(value))
            {
                _message.Text = "请先选择或输入一个文件夹。";
                return;
            }

            try
            {
                SelectedPath = System.IO.Path.GetFullPath(value);
                DialogResult = true;
                Close();
            }
            catch (Exception ex)
            {
                _message.Text = "路径格式不正确：" + ex.Message;
            }
        }

        private static string FindExistingDirectory(string path)
        {
            path = NormalizePath(path);
            if (string.IsNullOrWhiteSpace(path)) return null;

            try
            {
                if (Directory.Exists(path)) return path;
                var current = new DirectoryInfo(path);
                while (current != null)
                {
                    if (current.Exists) return current.FullName;
                    current = current.Parent;
                }
            }
            catch
            {
                return null;
            }
            return null;
        }

        private static string NormalizePath(string value)
        {
            if (string.IsNullOrWhiteSpace(value)) return string.Empty;
            value = Environment.ExpandEnvironmentVariables(value.Trim().Trim('"'));
            try
            {
                return System.IO.Path.GetFullPath(value);
            }
            catch
            {
                return value;
            }
        }
    }

}






