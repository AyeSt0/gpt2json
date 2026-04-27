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
                _dirBox.Text = DefaultInstallPath();
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
                Text = "GPT2JSON 安装",
                Foreground = Brushes.White,
                FontSize = 43,
                FontWeight = FontWeights.Bold,
                Effect = new DropShadowEffect { BlurRadius = 18, ShadowDepth = 0, Color = Color.FromRgb(43, 137, 255), Opacity = 0.18 }
            };
            Canvas.SetLeft(title, 410);
            Canvas.SetTop(title, 154);
            overlay.Children.Add(title);

            var desc = new TextBlock
            {
                Text = "轻量独立的 Sub2API / CPA JSON 导出工具",
                Foreground = new SolidColorBrush(Color.FromRgb(161, 179, 214)),
                FontSize = 16
            };
            Canvas.SetLeft(desc, 412);
            Canvas.SetTop(desc, 214);
            overlay.Children.Add(desc);

            var features = new WrapPanel();
            features.Children.Add(FeaturePill("◇", "协议优先"));
            features.Children.Add(FeaturePill("▱", "批量导出"));
            features.Children.Add(FeaturePill("↯", "本地处理"));
            Canvas.SetLeft(features, 410);
            Canvas.SetTop(features, 256);
            overlay.Children.Add(features);

            var label = new TextBlock
            {
                Text = "安装位置",
                Foreground = new SolidColorBrush(Color.FromRgb(231, 240, 255)),
                FontSize = 15,
                FontWeight = FontWeights.SemiBold
            };
            Canvas.SetLeft(label, 410);
            Canvas.SetTop(label, 326);
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
            Canvas.SetTop(pathBorder, 362);
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
            Canvas.SetTop(progress, 433);
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
            Canvas.SetTop(status, 448);
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
            Canvas.SetTop(install, 464);
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
            Canvas.SetTop(cancel, 464);
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
                _dirBox.Text = dlg.SelectedPath;
        }

        private static string DefaultInstallPath()
        {
            return System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "GPT2JSON");
        }

        private async Task InstallAsync()
        {
            if (_dirBox == null || string.IsNullOrWhiteSpace(_dirBox.Text))
            {
                MessageBox.Show("请先选择安装目录。", AppName, MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            SetBusy(true, "正在释放安装核心…", 18);
            try
            {
                string installerPath = ExtractInstaller();
                Directory.CreateDirectory(_dirBox.Text);
                SetBusy(true, "安装核心已就绪，正在写入文件…", 42);
                int code = await Task.Run(delegate
                {
                    var psi = new ProcessStartInfo
                    {
                        FileName = installerPath,
                        Arguments = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=\"" + _dirBox.Text + "\"",
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
        private readonly TextBox _pathBox;
        private readonly ListBox _folderList;
        private readonly TextBlock _hint;

        public string SelectedPath { get; private set; }

        public InstallDirectoryDialog(string initialPath, string defaultPath)
        {
            _defaultPath = NormalizePath(defaultPath);
            SelectedPath = NormalizePath(string.IsNullOrWhiteSpace(initialPath) ? _defaultPath : initialPath);

            Title = "选择 GPT2JSON 安装目录";
            Width = 650;
            Height = 490;
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
            glowBrush.GradientStops.Add(new GradientStop(Color.FromArgb(125, 70, 202, 255), 0));
            glowBrush.GradientStops.Add(new GradientStop(Color.FromArgb(18, 146, 74, 255), 0.68));
            glowBrush.GradientStops.Add(new GradientStop(Color.FromArgb(0, 0, 0, 0), 1));
            var glow = new System.Windows.Shapes.Ellipse
            {
                Width = 430,
                Height = 270,
                Fill = glowBrush,
                HorizontalAlignment = System.Windows.HorizontalAlignment.Left,
                VerticalAlignment = System.Windows.VerticalAlignment.Top,
                Margin = new Thickness(-72, -76, 0, 0),
                IsHitTestVisible = false
            };
            root.Children.Add(glow);

            var cardBrush = new LinearGradientBrush();
            cardBrush.StartPoint = new Point(0, 0);
            cardBrush.EndPoint = new Point(1, 1);
            cardBrush.GradientStops.Add(new GradientStop(Color.FromRgb(12, 24, 56), 0));
            cardBrush.GradientStops.Add(new GradientStop(Color.FromRgb(23, 34, 78), 0.52));
            cardBrush.GradientStops.Add(new GradientStop(Color.FromRgb(48, 30, 88), 1));

            var card = new Border
            {
                Width = 604,
                Height = 430,
                CornerRadius = new CornerRadius(34),
                Background = cardBrush,
                BorderBrush = new LinearGradientBrush(Color.FromArgb(155, 75, 213, 255), Color.FromArgb(140, 188, 86, 255), 0),
                BorderThickness = new Thickness(1),
                HorizontalAlignment = System.Windows.HorizontalAlignment.Center,
                VerticalAlignment = System.Windows.VerticalAlignment.Center,
                Effect = new DropShadowEffect
                {
                    BlurRadius = 34,
                    ShadowDepth = 0,
                    Opacity = 0.45,
                    Color = Color.FromRgb(0, 0, 0)
                }
            };
            root.Children.Add(card);

            var panel = new Canvas { Width = 604, Height = 430 };
            card.Child = panel;

            var dragZone = new Border
            {
                Width = 604,
                Height = 78,
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

            var title = new TextBlock
            {
                Text = "选择安装目录",
                Foreground = Brushes.White,
                FontSize = 24,
                FontWeight = FontWeights.Bold,
                Effect = new DropShadowEffect { BlurRadius = 16, ShadowDepth = 0, Color = Color.FromRgb(39, 183, 255), Opacity = 0.22 }
            };
            Canvas.SetLeft(title, 36);
            Canvas.SetTop(title, 28);
            panel.Children.Add(title);

            var subtitle = new TextBlock
            {
                Text = "可直接输入路径，也可以从常用位置快速跳转",
                Foreground = new SolidColorBrush(Color.FromRgb(151, 176, 219)),
                FontSize = 12
            };
            Canvas.SetLeft(subtitle, 38);
            Canvas.SetTop(subtitle, 61);
            panel.Children.Add(subtitle);

            var close = new Button
            {
                Content = "×",
                Width = 38,
                Height = 32,
                FontSize = 18,
                Foreground = new SolidColorBrush(Color.FromRgb(220, 230, 255)),
                Background = new SolidColorBrush(Color.FromArgb(34, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(56, 255, 255, 255)),
                Style = InstallerWindow.RoundedButtonStyle(16)
            };
            close.Click += delegate { DialogResult = false; Close(); };
            Canvas.SetLeft(close, 536);
            Canvas.SetTop(close, 26);
            panel.Children.Add(close);

            var pathLabel = new TextBlock
            {
                Text = "当前路径",
                Foreground = new SolidColorBrush(Color.FromRgb(224, 237, 255)),
                FontSize = 13,
                FontWeight = FontWeights.SemiBold
            };
            Canvas.SetLeft(pathLabel, 38);
            Canvas.SetTop(pathLabel, 98);
            panel.Children.Add(pathLabel);

            var pathBorder = new Border
            {
                Width = 528,
                Height = 50,
                CornerRadius = new CornerRadius(17),
                Background = new SolidColorBrush(Color.FromArgb(50, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(105, 124, 202, 255)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(16, 0, 14, 0)
            };
            var pathGrid = new Grid();
            pathGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(28) });
            pathGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            var pathIcon = new TextBlock
            {
                Text = "\uE8B7",
                FontFamily = new FontFamily("Segoe MDL2 Assets"),
                Foreground = new SolidColorBrush(Color.FromRgb(112, 205, 255)),
                FontSize = 17,
                VerticalAlignment = System.Windows.VerticalAlignment.Center
            };
            pathGrid.Children.Add(pathIcon);
            _pathBox = new TextBox
            {
                Text = SelectedPath,
                Foreground = new SolidColorBrush(Color.FromRgb(232, 243, 255)),
                Background = Brushes.Transparent,
                BorderThickness = new Thickness(0),
                FontSize = 14,
                VerticalContentAlignment = System.Windows.VerticalAlignment.Center,
                CaretBrush = Brushes.White
            };
            Grid.SetColumn(_pathBox, 1);
            pathGrid.Children.Add(_pathBox);
            pathBorder.Child = pathGrid;
            Canvas.SetLeft(pathBorder, 38);
            Canvas.SetTop(pathBorder, 121);
            panel.Children.Add(pathBorder);

            var quick = new WrapPanel();
            quick.Children.Add(QuickButton("默认安装", _defaultPath));
            quick.Children.Add(QuickButton("用户目录", Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)));
            quick.Children.Add(QuickButton("桌面", Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory)));
            quick.Children.Add(QuickButton("下载", System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads")));
            quick.Children.Add(QuickButton("Program Files", Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles)));
            Canvas.SetLeft(quick, 38);
            Canvas.SetTop(quick, 184);
            panel.Children.Add(quick);

            var listBorder = new Border
            {
                Width = 528,
                Height = 132,
                CornerRadius = new CornerRadius(20),
                Background = new SolidColorBrush(Color.FromArgb(28, 7, 12, 34)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(70, 111, 174, 255)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(10)
            };
            _folderList = new ListBox
            {
                Background = Brushes.Transparent,
                BorderThickness = new Thickness(0),
                Foreground = new SolidColorBrush(Color.FromRgb(220, 234, 255)),
                FontSize = 13
            };
            _folderList.ItemContainerStyle = FolderListItemStyle();
            _folderList.MouseDoubleClick += delegate { EnterSelectedFolder(); };
            _folderList.KeyDown += delegate(object sender, System.Windows.Input.KeyEventArgs args)
            {
                if (args.Key == Key.Enter) EnterSelectedFolder();
            };
            listBorder.Child = _folderList;
            Canvas.SetLeft(listBorder, 38);
            Canvas.SetTop(listBorder, 230);
            panel.Children.Add(listBorder);

            _hint = new TextBlock
            {
                Text = "提示：双击文件夹进入；路径不存在时，安装阶段会自动创建。",
                Foreground = new SolidColorBrush(Color.FromRgb(139, 164, 205)),
                FontSize = 12
            };
            Canvas.SetLeft(_hint, 42);
            Canvas.SetTop(_hint, 374);
            panel.Children.Add(_hint);

            var mkdir = new Button
            {
                Content = "+ 新建 GPT2JSON 文件夹",
                Width = 176,
                Height = 38,
                FontSize = 13,
                Foreground = new SolidColorBrush(Color.FromRgb(223, 236, 255)),
                Background = new SolidColorBrush(Color.FromArgb(28, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(70, 133, 198, 255)),
                Style = InstallerWindow.RoundedButtonStyle(14)
            };
            mkdir.Click += delegate { CreateFolderUnderCurrent(); };
            Canvas.SetLeft(mkdir, 38);
            Canvas.SetTop(mkdir, 398);
            panel.Children.Add(mkdir);

            var cancel = new Button
            {
                Content = "取消",
                Width = 112,
                Height = 42,
                FontSize = 14,
                Foreground = new SolidColorBrush(Color.FromRgb(218, 230, 255)),
                Background = new SolidColorBrush(Color.FromArgb(28, 255, 255, 255)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(76, 163, 190, 255)),
                Style = InstallerWindow.RoundedButtonStyle(16)
            };
            cancel.Click += delegate { DialogResult = false; Close(); };
            Canvas.SetLeft(cancel, 318);
            Canvas.SetTop(cancel, 394);
            panel.Children.Add(cancel);

            var use = new Button
            {
                Content = "使用此目录",
                Width = 136,
                Height = 42,
                FontSize = 15,
                FontWeight = FontWeights.Bold,
                Foreground = Brushes.White,
                Background = new LinearGradientBrush(Color.FromRgb(28, 186, 255), Color.FromRgb(174, 70, 255), 0),
                BorderBrush = new SolidColorBrush(Color.FromArgb(132, 210, 235, 255)),
                Style = InstallerWindow.RoundedButtonStyle(16)
            };
            use.Click += delegate { UseCurrentPath(); };
            Canvas.SetLeft(use, 438);
            Canvas.SetTop(use, 394);
            panel.Children.Add(use);

            Loaded += delegate { RefreshFolderList(false); };
        }

        private Button QuickButton(string label, string path)
        {
            var button = new Button
            {
                Content = label,
                Height = 30,
                Margin = new Thickness(0, 0, 8, 8),
                FontSize = 12,
                Foreground = new SolidColorBrush(Color.FromRgb(219, 234, 255)),
                Background = new LinearGradientBrush(Color.FromArgb(40, 255, 255, 255), Color.FromArgb(22, 92, 172, 255), 0),
                BorderBrush = new SolidColorBrush(Color.FromArgb(68, 126, 206, 255)),
                Style = InstallerWindow.RoundedButtonStyle(13)
            };
            button.Click += delegate
            {
                _pathBox.Text = NormalizePath(path);
                RefreshFolderList(true);
            };
            return button;
        }

        private static Style FolderListItemStyle()
        {
            var style = new Style(typeof(ListBoxItem));
            style.Setters.Add(new Setter(Control.PaddingProperty, new Thickness(10, 7, 10, 7)));
            style.Setters.Add(new Setter(Control.MarginProperty, new Thickness(0, 0, 0, 3)));
            style.Setters.Add(new Setter(Control.ForegroundProperty, new SolidColorBrush(Color.FromRgb(220, 234, 255))));
            style.Setters.Add(new Setter(Control.BackgroundProperty, Brushes.Transparent));
            style.Setters.Add(new Setter(Control.BorderThicknessProperty, new Thickness(0)));
            style.Setters.Add(new Setter(Control.HorizontalContentAlignmentProperty, System.Windows.HorizontalAlignment.Stretch));
            return style;
        }

        private void EnterSelectedFolder()
        {
            var choice = _folderList.SelectedItem as DirectoryChoice;
            if (choice == null) return;
            _pathBox.Text = choice.Path;
            RefreshFolderList(true);
        }

        private void RefreshFolderList(bool pathWasChosen)
        {
            _folderList.Items.Clear();
            string typedPath = NormalizePath(_pathBox.Text);
            string existing = FindExistingDirectory(typedPath);
            if (string.IsNullOrEmpty(existing))
            {
                _hint.Text = "这个路径暂时无法浏览，但只要磁盘有效，安装时仍可尝试创建。";
                return;
            }

            if (pathWasChosen)
                _pathBox.Text = existing;

            var parent = Directory.GetParent(existing);
            if (parent != null)
            {
                _folderList.Items.Add(new DirectoryChoice
                {
                    Text = "返回上一级  ·  " + parent.FullName,
                    Path = parent.FullName,
                    IsParent = true
                });
            }

            try
            {
                string[] directories = Directory.GetDirectories(existing);
                Array.Sort(directories, StringComparer.CurrentCultureIgnoreCase);
                int shown = 0;
                for (int i = 0; i < directories.Length && shown < 80; i++)
                {
                    string dir = directories[i];
                    string name = System.IO.Path.GetFileName(dir);
                    if (string.IsNullOrEmpty(name)) name = dir;
                    _folderList.Items.Add(new DirectoryChoice { Text = name, Path = dir, IsParent = false });
                    shown++;
                }
                _hint.Text = directories.Length == 0
                    ? "当前目录下面没有子文件夹，可以直接使用此目录。"
                    : "双击进入子目录；如果只是想安装到当前路径，点「使用此目录」。";
            }
            catch (Exception ex)
            {
                _hint.Text = "目录可用，但读取子目录失败：" + ex.Message;
            }
        }

        private void CreateFolderUnderCurrent()
        {
            try
            {
                string baseDir = FindExistingDirectory(_pathBox.Text);
                if (string.IsNullOrEmpty(baseDir)) baseDir = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);

                string candidate = System.IO.Path.Combine(baseDir, "GPT2JSON");
                int index = 2;
                while (Directory.Exists(candidate))
                {
                    candidate = System.IO.Path.Combine(baseDir, "GPT2JSON-" + index.ToString());
                    index++;
                }

                Directory.CreateDirectory(candidate);
                _pathBox.Text = candidate;
                RefreshFolderList(true);
                _hint.Text = "已经创建好新文件夹，直接使用即可。";
            }
            catch (Exception ex)
            {
                _hint.Text = "新建文件夹失败：" + ex.Message;
            }
        }

        private void UseCurrentPath()
        {
            string value = NormalizePath(_pathBox.Text);
            if (string.IsNullOrWhiteSpace(value))
            {
                _hint.Text = "先填一个安装目录再继续。";
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
                _hint.Text = "路径格式不正确：" + ex.Message;
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

    internal sealed class DirectoryChoice
    {
        public string Text { get; set; }
        public string Path { get; set; }
        public bool IsParent { get; set; }

        public override string ToString()
        {
            return (IsParent ? "↖  " : "▸  ") + Text;
        }
    }
}






